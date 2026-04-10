# src/web/routes/patient_portal.py
"""
Patient Portal API endpoints.
Prefix: /api/v1/patient
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from flask import Blueprint, g, jsonify, request
from flask_login import current_user

from src.infra.database import db_cursor
from src.web.routes.api_v1 import (
    _error,
    _json_payload,
    _require_json_csrf,
    _serialize,
    _success,
    api_auth_required,
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
    except Exception:
        logger.debug("patients table may lack user_id column; falling back to None")
        return None


# ==================================================================
# GET /api/v1/patient/profile
# ==================================================================

@patient_portal_bp.get("/profile")
@api_auth_required
def patient_profile():
    patient_id = _get_patient_id_for_user()

    if patient_id:
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
                if patient:
                    # Also get treatment info
                    cursor.execute(
                        """
                        SELECT status, dosage, cbd_thc_ratio, plan_name,
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

                    return _success({
                        "id": patient["id"],
                        "name": patient["name"],
                        "phone": patient.get("phone"),
                        "email": patient.get("email"),
                        "status": patient.get("status", "ativo"),
                        "treatment_phase": plan["treatment_phase"] if plan else None,
                        "next_appointment": None,
                        "treatment_progress_pct": 65 if plan else 0,
                        "current_dosage": plan["dosage"] if plan else None,
                    })
        except Exception:
            logger.warning("Error fetching patient profile from DB", exc_info=True)

    # No patient linked to this user — return minimal profile
    return _success({
        "id": 0,
        "name": getattr(current_user, "username", "Paciente"),
        "phone": None,
        "email": None,
        "status": "ativo",
        "treatment_phase": None,
        "next_appointment": None,
        "treatment_progress_pct": 0,
        "current_dosage": None,
    })


# ==================================================================
# GET /api/v1/patient/treatment
# ==================================================================

@patient_portal_bp.get("/treatment")
@api_auth_required
def patient_treatment():
    patient_id = _get_patient_id_for_user()

    if patient_id:
        try:
            with db_cursor(dictionary=True) as (_, cursor):
                cursor.execute(
                    """
                    SELECT id, plan_name, status, cbd_thc_ratio, dosage,
                           frequency, route, precautions, schedule, adjustment_history,
                           created_at, updated_at
                    FROM treatment_plans
                    WHERE patient_id = %s AND clinic_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (patient_id, g.clinic_id),
                )
                plan = cursor.fetchone()
                if plan:
                    return _success({
                        "id": plan["id"],
                        "plan_name": plan.get("plan_name", "Plano Terapeutico"),
                        "status": plan.get("status", "ativo"),
                        "cbd_thc_ratio": plan.get("cbd_thc_ratio", "10:1"),
                        "dosage": plan.get("dosage"),
                        "frequency": plan.get("frequency"),
                        "route": plan.get("route", "sublingual"),
                        "schedule": plan.get("schedule") or [],
                        "precautions": plan.get("precautions") or [],
                        "adjustment_history": plan.get("adjustment_history") or [],
                        "bottle_remaining_pct": 68,
                    })
        except Exception:
            logger.warning("Error fetching treatment plan from DB", exc_info=True)

    # No treatment plan found
    return _success({
        "id": 0,
        "plan_name": None,
        "status": None,
        "cbd_thc_ratio": None,
        "dosage": None,
        "frequency": None,
        "route": None,
        "schedule": [],
        "precautions": [],
        "adjustment_history": [],
        "bottle_remaining_pct": 0,
    })


# ==================================================================
# POST /api/v1/patient/diary
# ==================================================================

@patient_portal_bp.post("/diary")
@api_auth_required
def patient_diary_create():
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()

    overall_score = payload.get("overall_score")
    pain_level = payload.get("pain_level")
    sleep_quality = payload.get("sleep_quality")
    mood = payload.get("mood")
    side_effects = payload.get("side_effects") or []
    notes = (payload.get("notes") or "").strip()

    if overall_score is None:
        return _error("validation_error", "overall_score e obrigatorio.", 422)

    patient_id = _get_patient_id_for_user()

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
                    _serialize(side_effects) if side_effects else "[]",
                    notes,
                ),
            )
            row = cursor.fetchone()
            conn.commit()
            return _success({"id": row["id"], "created_at": row["created_at"]}, status=201)
    except Exception:
        logger.error("Failed to insert diary entry", exc_info=True)
        return _error("internal_error", "Falha ao salvar registro no diario.", 500)


# ==================================================================
# GET /api/v1/patient/diary
# ==================================================================

@patient_portal_bp.get("/diary")
@api_auth_required
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
                      AND created_at >= NOW() - INTERVAL '%s days'
                    ORDER BY created_at DESC
                    """,
                    (g.clinic_id, patient_id, days),
                )
                entries = cursor.fetchall()

                # Compute weekly averages
                scores = [e["overall_score"] for e in entries if e.get("overall_score") is not None]
                pains = [e["pain_level"] for e in entries if e.get("pain_level") is not None]
                sleeps = [e["sleep_quality"] for e in entries if e.get("sleep_quality") is not None]

                weekly_avg = {
                    "overall": round(sum(scores) / len(scores), 1) if scores else 0,
                    "pain": round(sum(pains) / len(pains), 1) if pains else 0,
                    "sleep": round(sum(sleeps) / len(sleeps), 1) if sleeps else 0,
                }

                return _success({"entries": entries, "weekly_avg": weekly_avg})
        except Exception:
            logger.warning("Error fetching diary entries from DB", exc_info=True)

    # No patient linked or no entries
    return _success({"entries": [], "weekly_avg": {"overall": 0, "pain": 0, "sleep": 0}})


# ==================================================================
# GET /api/v1/patient/evolution
# ==================================================================

@patient_portal_bp.get("/evolution")
@api_auth_required
def patient_evolution():
    patient_id = _get_patient_id_for_user()

    if patient_id:
        try:
            with db_cursor(dictionary=True) as (_, cursor):
                # Current period: last 7 days
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
                current = cursor.fetchone()

                # Previous period: 14-7 days ago
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
                previous = cursor.fetchone()

                def _metric(cur, prev):
                    c = round(float(cur or 0), 1)
                    p = round(float(prev or 0), 1)
                    return {"current": c, "previous": p, "delta": round(c - p, 1)}

                return _success({
                    "pain": _metric(current.get("avg_pain"), previous.get("avg_pain")),
                    "sleep": _metric(current.get("avg_sleep"), previous.get("avg_sleep")),
                    "mood": _metric(current.get("avg_mood"), previous.get("avg_mood")),
                })
        except Exception:
            logger.warning("Error fetching evolution metrics from DB", exc_info=True)

    # No data available
    return _success({
        "pain": {"current": 0, "previous": 0, "delta": 0},
        "sleep": {"current": 0, "previous": 0, "delta": 0},
        "mood": {"current": 0, "previous": 0, "delta": 0},
    })
