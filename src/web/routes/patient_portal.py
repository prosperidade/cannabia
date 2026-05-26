# src/web/routes/patient_portal.py
"""
Patient Portal API endpoints.
Prefix: /api/v1/patient
"""

from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
from typing import Any, Optional

from flask import Blueprint, g, request
from flask_login import current_user
from psycopg2 import DatabaseError, OperationalError

from src.infra.database import db_cursor
from src.web.routes.api_v1 import (
    _error,
    _json_payload,
    _require_json_csrf,
    _serialize,
    _success,
    api_role_required,
)

logger = logging.getLogger("cannabia.patient_portal")

patient_portal_bp = Blueprint("patient_portal", __name__, url_prefix="/api/v1/patient")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _get_patient_id_for_user() -> Optional[int]:
    """Resolve the patient_id linked to the current authenticated user."""
    user_id = int(current_user.id)
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                """
                SELECT id FROM patients
                WHERE user_id = %s AND clinic_id = %s
                LIMIT 1
                """,
                (user_id, g.clinic_id),
            )
            row = cursor.fetchone()
            return row["id"] if row else None
    except DatabaseError:
        logger.debug("patients table may lack user_id column; falling back to None")
        return None


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _iso_date(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    return None


def _parse_ratio(raw: Any) -> tuple[int, int]:
    text = str(raw or "").strip().lower().replace("cbd", "").replace("thc", "")
    text = text.replace("/", ":").replace("-", ":")
    parts = [p.strip() for p in text.split(":") if p.strip()]
    if len(parts) < 2:
        return 0, 0
    return _as_int(parts[0]), _as_int(parts[1])


def _bottle_remaining_pct(plan: dict | None) -> int | None:
    if not plan:
        return None
    capacity = plan.get("bottle_capacity_ml")
    consumed = plan.get("bottle_consumed_ml")
    if capacity is None or consumed is None:
        return None
    try:
        capacity_f = float(capacity)
        consumed_f = float(consumed)
    except (TypeError, ValueError):
        return None
    if capacity_f <= 0:
        return None
    remaining = round(((capacity_f - consumed_f) / capacity_f) * 100)
    return max(0, min(100, int(remaining)))


def _treatment_day(plan_row: dict | None) -> int:
    if not plan_row or not plan_row.get("created_at"):
        return 0
    created = plan_row["created_at"]
    if not isinstance(created, datetime):
        return 0
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - created
    return max(0, delta.days)


# ==================================================================
# GET /api/v1/patient/profile
# ==================================================================
#
# Shape (envelope esperado pelo frontend /p/dashboard):
#   {
#     "patient":     {id, name, phone, email, status, treatment_status,
#                     treatment_phase, treatment_day, treatment_total_days},
#     "appointment": {date, time, doctor, modality}            # ou None
#     "treatment":   {product, dose, frequency, cbd_mg, thc_mg} # ou None
#   }
#
# Campos sem fonte preenchida no banco sao retornados como None. O frontend
# decide a apresentacao sem fingir que placeholders sao dados reais.

def _empty_profile_envelope(name: str) -> dict:
    return {
        "patient": {
            "id": 0,
            "name": name,
            "phone": None,
            "email": None,
            "status": "ativo",
            "treatment_status": None,
            "treatment_phase": None,
            "treatment_day": 0,
            "treatment_total_days": None,
        },
        "appointment": None,
        "treatment": None,
    }


def _format_appointment(row: dict | None) -> dict | None:
    """Monta o sub-objeto appointment a partir de uma linha de appointments."""
    if not row:
        return None
    when = row.get("appointment_date")
    if when is None:
        return None
    # appointment_date e TIMESTAMP — formata em PT-BR curto.
    months = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    date_str = f"{when.day:02d} {months[when.month - 1]}"
    time_str = when.strftime("%H:%M")
    return {
        "date": date_str,
        "time": time_str,
        "doctor": row.get("doctor"),
        "modality": row.get("appointment_type"),
    }


def _format_treatment(plan: dict | None) -> dict | None:
    """Monta o sub-objeto treatment a partir de uma linha de treatment_plans."""
    if not plan:
        return None
    return {
        "product": plan.get("plan_name") or "Plano Terapeutico",
        "dose": plan.get("dosage"),
        "frequency": plan.get("frequency"),
        # TODO: parsing de cbd/thc a partir de ratio + dosage exige unidades
        # padronizadas; fica para sprint dedicada de prescricao estruturada.
        "cbd_mg": None,
        "thc_mg": None,
    }


def _format_patient_block(patient_row: dict, plan_row: dict | None) -> dict:
    """Monta o sub-objeto patient incluindo dados derivados do plano."""
    return {
        "id": patient_row["id"],
        "name": patient_row["name"],
        "phone": patient_row.get("phone"),
        "email": patient_row.get("email"),
        "status": patient_row.get("status", "ativo"),
        "treatment_status": plan_row.get("status") if plan_row else None,
        "treatment_phase": plan_row.get("treatment_phase") if plan_row else None,
        "treatment_day": _treatment_day(plan_row),
        "treatment_total_days": plan_row.get("duration_days") if plan_row else None,
    }


@patient_portal_bp.get("/profile")
@api_role_required("Paciente")
def patient_profile():
    patient_id = _get_patient_id_for_user()
    fallback_name = getattr(current_user, "username", "Paciente")

    if not patient_id:
        return _success(_empty_profile_envelope(fallback_name))

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                """
                SELECT id, name, phone, email, status, created_at
                FROM patients
                WHERE id = %s AND clinic_id = %s
                """,
                (patient_id, g.clinic_id),
            )
            patient = cursor.fetchone()
            if not patient:
                return _success(_empty_profile_envelope(fallback_name))

            cursor.execute(
                """
                SELECT status, dosage, cbd_thc_ratio, plan_name, frequency,
                       created_at, duration_days,
                       CASE WHEN next_return_date IS NULL THEN 'manutencao'
                             WHEN next_return_date > NOW() THEN 'titulacao'
                             ELSE 'retorno_pendente'
                       END AS treatment_phase
                FROM treatment_plans
                WHERE patient_id = %s AND clinic_id = %s
                ORDER BY created_at DESC LIMIT 1
                """,
                (patient_id, g.clinic_id),
            )
            plan = cursor.fetchone()

            cursor.execute(
                """
                SELECT a.id, a.appointment_date, a.status, a.appointment_type,
                       COALESCE(NULLIF(u.full_name, ''), u.username) AS doctor
                FROM appointments a
                LEFT JOIN users u ON u.id = a.doctor_id
                WHERE a.patient_id = %s AND a.clinic_id = %s
                  AND a.appointment_date >= NOW()
                ORDER BY a.appointment_date ASC
                LIMIT 1
                """,
                (patient_id, g.clinic_id),
            )
            next_appt = cursor.fetchone()

            return _success({
                "patient": _format_patient_block(patient, plan),
                "appointment": _format_appointment(next_appt),
                "treatment": _format_treatment(plan),
            })
    except OperationalError:
        logger.error("DB unavailable on patient_portal.get_profile", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, TypeError, ValueError, KeyError, AttributeError, IndexError):
        logger.warning("Error fetching patient profile from DB", exc_info=True)
        return _success(_empty_profile_envelope(fallback_name))


# ==================================================================
# GET /api/v1/patient/treatment
# ==================================================================

def _empty_treatment_envelope() -> dict:
    return {
        "protocol": None,
        "schedule": [],
        "instructions": {
            "doctor": None,
            "notes": None,
            "precautions": [],
        },
        "monitoring": {
            "observe": [],
            "contact_when": [],
        },
        "history": [],
    }


def _format_schedule_slots(value: Any) -> list[dict]:
    slots = []
    for index, item in enumerate(_as_list(value)):
        if isinstance(item, dict):
            period = item.get("period") or item.get("label") or f"Dose {index + 1}"
            slots.append({
                "period": period,
                "icon": item.get("icon") or "schedule",
                "time": item.get("time") or item.get("at") or "",
                "dose": item.get("dose") or item.get("dosage") or "",
                "taken": bool(item.get("taken", False)),
            })
        elif item:
            slots.append({
                "period": str(item),
                "icon": "schedule",
                "time": "",
                "dose": "",
                "taken": False,
            })
    return slots


def _format_adjustment_history(value: Any) -> list[dict]:
    history = []
    for item in _as_list(value):
        if isinstance(item, dict):
            history.append({
                "date": item.get("date") or item.get("created_at") or "",
                "change": item.get("change") or item.get("title") or item.get("description") or "",
                "reason": item.get("reason") or item.get("notes") or "",
            })
    return history


def _format_treatment_envelope(plan: dict) -> dict:
    cbd_ratio, thc_ratio = _parse_ratio(plan.get("cbd_thc_ratio"))
    return {
        "protocol": {
            "id": plan["id"],
            "name": plan.get("plan_name") or "Plano Terapeutico",
            "status": plan.get("status"),
            "phase": plan.get("treatment_phase"),
            "start_date": _iso_date(plan.get("created_at")),
            "product": plan.get("plan_name"),
            "concentration": plan.get("cbd_thc_ratio"),
            "route": plan.get("route"),
            "dose": plan.get("dosage"),
            "frequency": plan.get("frequency"),
            "cbd_ratio": cbd_ratio,
            "thc_ratio": thc_ratio,
            "bottle_remaining": _bottle_remaining_pct(plan),
            "bottle_end_estimate": None,
            "duration_days": plan.get("duration_days"),
        },
        "schedule": _format_schedule_slots(plan.get("schedule")),
        "instructions": {
            "doctor": None,
            "notes": plan.get("plan_description"),
            "precautions": _as_list(plan.get("precautions")),
        },
        "monitoring": {
            "observe": [],
            "contact_when": _as_list(plan.get("precautions")),
        },
        "history": _format_adjustment_history(plan.get("adjustment_history")),
    }


@patient_portal_bp.get("/treatment")
@api_role_required("Paciente")
def patient_treatment():
    patient_id = _get_patient_id_for_user()

    if patient_id:
        try:
            with db_cursor(dictionary=True) as (_, cursor):
                cursor.execute(
                    """
                    SELECT id, plan_name, plan_description, status, cbd_thc_ratio, dosage,
                           frequency, route, precautions, schedule, adjustment_history,
                           created_at, updated_at, duration_days, bottle_capacity_ml,
                           bottle_consumed_ml,
                           CASE WHEN next_return_date IS NULL THEN 'manutencao'
                                WHEN next_return_date > NOW() THEN 'titulacao'
                                ELSE 'retorno_pendente'
                           END AS treatment_phase
                    FROM treatment_plans
                    WHERE patient_id = %s AND clinic_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (patient_id, g.clinic_id),
                )
                plan = cursor.fetchone()
                if plan:
                    return _success(_format_treatment_envelope(plan))
        except OperationalError:
            logger.error("DB unavailable on patient_portal.get_treatment", exc_info=True)
            return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
        except (DatabaseError, TypeError, ValueError, KeyError, AttributeError):
            logger.warning("Error fetching treatment plan from DB", exc_info=True)

    # No treatment plan found
    return _success(_empty_treatment_envelope())


# ==================================================================
# GET /api/v1/patient/appointments
# ==================================================================
#
# Lista de consultas do paciente. Retorna {upcoming: [...], past: [...]}
# com formatacao basica de data/hora em PT-BR.

def _format_appointment_row(row: dict) -> dict:
    when = row["appointment_date"]
    months = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    return {
        "id": row["id"],
        "date": f"{when.day:02d} {months[when.month - 1]} {when.year}",
        "time": when.strftime("%H:%M"),
        "iso": when.isoformat(),
        "status": row.get("status") or "agendado",
        "doctor": row.get("doctor"),
        "modality": row.get("appointment_type"),
        "notes": row.get("notes"),
    }


@patient_portal_bp.get("/appointments")
@api_role_required("Paciente")
def patient_appointments():
    patient_id = _get_patient_id_for_user()

    if not patient_id:
        return _success({"upcoming": [], "past": []})

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                """
                SELECT a.id, a.appointment_date, a.status, a.notes, a.appointment_type,
                       COALESCE(NULLIF(u.full_name, ''), u.username) AS doctor
                FROM appointments a
                LEFT JOIN users u ON u.id = a.doctor_id
                WHERE a.patient_id = %s AND a.clinic_id = %s
                  AND a.appointment_date >= NOW()
                ORDER BY a.appointment_date ASC
                LIMIT 20
                """,
                (patient_id, g.clinic_id),
            )
            upcoming = [_format_appointment_row(r) for r in cursor.fetchall()]

            cursor.execute(
                """
                SELECT a.id, a.appointment_date, a.status, a.notes, a.appointment_type,
                       COALESCE(NULLIF(u.full_name, ''), u.username) AS doctor
                FROM appointments a
                LEFT JOIN users u ON u.id = a.doctor_id
                WHERE a.patient_id = %s AND a.clinic_id = %s
                  AND a.appointment_date < NOW()
                ORDER BY a.appointment_date DESC
                LIMIT 20
                """,
                (patient_id, g.clinic_id),
            )
            past = [_format_appointment_row(r) for r in cursor.fetchall()]

            return _success({"upcoming": upcoming, "past": past})
    except OperationalError:
        logger.error("DB unavailable on patient_portal.get_appointments", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except (DatabaseError, TypeError, ValueError, KeyError, AttributeError, IndexError):
        logger.warning("Error fetching patient appointments from DB", exc_info=True)
        return _success({"upcoming": [], "past": []})


# ==================================================================
# POST /api/v1/patient/diary
# ==================================================================

@patient_portal_bp.post("/diary")
@api_role_required("Paciente")
def patient_diary_create():
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()

    overall_score = payload.get("overall_score")
    if overall_score is None:
        overall_score = payload.get("overall")
    pain_level = payload.get("pain_level")
    sleep_quality = payload.get("sleep_quality")
    mood = payload.get("mood")
    side_effects = payload.get("side_effects") or []
    notes = (payload.get("notes") or "").strip()

    if overall_score is None:
        return _error("validation_error", "overall_score e obrigatorio.", 422)

    patient_id = _get_patient_id_for_user()
    if not patient_id:
        return _error("patient_not_linked", "Paciente nao vinculado ao usuario.", 403)

    try:
        with db_cursor(dictionary=True) as (conn, cursor):
            cursor.execute(
                """
                INSERT INTO symptom_diary
                    (clinic_id, patient_id, user_id, overall_score, pain_level,
                     sleep_quality, mood, side_effects, notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, NOW())
                RETURNING id, created_at
                """,
                (
                    g.clinic_id,
                    patient_id,
                    int(current_user.id),
                    overall_score,
                    pain_level,
                    sleep_quality,
                    mood,
                    json.dumps(_serialize(side_effects)) if side_effects else "[]",
                    notes,
                ),
            )
            row = cursor.fetchone()
            conn.commit()
            return _success({"id": row["id"], "created_at": row["created_at"]}, status=201)
    except (DatabaseError, TypeError, ValueError, KeyError):
        logger.error("Failed to insert diary entry", exc_info=True)
        return _error("internal_error", "Falha ao salvar registro no diario.", 500)


# ==================================================================
# GET /api/v1/patient/diary
# ==================================================================

def _format_diary_entry(row: dict) -> dict:
    created = row.get("created_at")
    if isinstance(created, datetime):
        date_str = created.date().isoformat()
    else:
        date_str = str(created or "").split("T")[0].split(" ")[0]

    overall_score = _as_int(row.get("overall_score"))
    return {
        "id": row.get("id"),
        "date": date_str,
        "created_at": created,
        "overall_score": overall_score,
        "overall": overall_score,
        "pain_level": _as_int(row.get("pain_level")),
        "sleep_quality": _as_int(row.get("sleep_quality")),
        "mood": _as_int(row.get("mood")),
        "side_effects": _as_list(row.get("side_effects")),
        "notes": row.get("notes") or "",
    }


@patient_portal_bp.get("/diary")
@api_role_required("Paciente")
def patient_diary_list():
    try:
        days = int(request.args.get("days", 30))
    except (TypeError, ValueError):
        days = 30
    days = max(1, min(days, 365))

    patient_id = _get_patient_id_for_user()

    if patient_id:
        try:
            with db_cursor(dictionary=True) as (_, cursor):
                cursor.execute(
                    """
                    SELECT id, overall_score, pain_level, sleep_quality, mood,
                           side_effects, notes, created_at
                    FROM symptom_diary
                    WHERE clinic_id = %s AND patient_id = %s
                      AND created_at >= NOW() - (%s * INTERVAL '1 day')
                    ORDER BY created_at DESC
                    """,
                    (g.clinic_id, patient_id, days),
                )
                entries = cursor.fetchall()
                formatted_entries = [_format_diary_entry(e) for e in entries]

                # Compute weekly averages
                scores = [e["overall_score"] for e in entries if e.get("overall_score") is not None]
                pains = [e["pain_level"] for e in entries if e.get("pain_level") is not None]
                sleeps = [e["sleep_quality"] for e in entries if e.get("sleep_quality") is not None]

                weekly_avg = {
                    "overall": round(sum(scores) / len(scores), 1) if scores else 0,
                    "pain": round(sum(pains) / len(pains), 1) if pains else 0,
                    "sleep": round(sum(sleeps) / len(sleeps), 1) if sleeps else 0,
                }

                return _success({"entries": formatted_entries, "weekly_avg": weekly_avg})
        except (DatabaseError, TypeError, ValueError, KeyError):
            logger.warning("Error fetching diary entries from DB", exc_info=True)

    # No patient linked or no entries
    return _success({"entries": [], "weekly_avg": {"overall": 0, "pain": 0, "sleep": 0}})


# ==================================================================
# GET /api/v1/patient/evolution
# ==================================================================
#
# Shape (envelope esperado pelo frontend /p/dashboard):
#   { "evolution": { "<key>": {"label", "value", "prev"} } }
#
# Diary scores sao 0-10; convertemos para 0-100. Dor (maior = pior) e
# invertida porque o frontend trata "value > prev" como melhora.

def _empty_evolution_envelope() -> dict:
    return {
        "evolution": {
            "pain": {"label": "Dor", "value": 0, "prev": 0},
            "sleep": {"label": "Sono", "value": 0, "prev": 0},
            "mood": {"label": "Humor", "value": 0, "prev": 0},
        }
    }


@patient_portal_bp.get("/evolution")
@api_role_required("Paciente")
def patient_evolution():
    patient_id = _get_patient_id_for_user()

    if not patient_id:
        return _success(_empty_evolution_envelope())

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                """
                SELECT
                    AVG(pain_level) AS avg_pain,
                    AVG(sleep_quality) AS avg_sleep,
                    AVG(overall_score) AS avg_mood
                FROM symptom_diary
                WHERE clinic_id = %s AND patient_id = %s
                  AND created_at >= NOW() - INTERVAL '7 days'
                """,
                (g.clinic_id, patient_id),
            )
            current = cursor.fetchone() or {}

            cursor.execute(
                """
                SELECT
                    AVG(pain_level) AS avg_pain,
                    AVG(sleep_quality) AS avg_sleep,
                    AVG(overall_score) AS avg_mood
                FROM symptom_diary
                WHERE clinic_id = %s AND patient_id = %s
                  AND created_at >= NOW() - INTERVAL '14 days'
                  AND created_at < NOW() - INTERVAL '7 days'
                """,
                (g.clinic_id, patient_id),
            )
            previous = cursor.fetchone() or {}

            def _scale(value, *, invert=False) -> int:
                if value is None:
                    return 0
                pct = round(float(value) * 10)
                if invert:
                    pct = 100 - pct
                return max(0, min(100, pct))

            def _metric(label: str, key: str, *, invert: bool = False) -> dict:
                return {
                    "label": label,
                    "value": _scale(current.get(key), invert=invert),
                    "prev": _scale(previous.get(key), invert=invert),
                }

            return _success({
                "evolution": {
                    "pain": _metric("Dor", "avg_pain", invert=True),
                    "sleep": _metric("Sono", "avg_sleep"),
                    "mood": _metric("Humor", "avg_mood"),
                }
            })
    except (DatabaseError, TypeError, ValueError, KeyError):
        logger.warning("Error fetching evolution metrics from DB", exc_info=True)
        return _success(_empty_evolution_envelope())
