# src/web/routes/telemetry.py
"""
Blueprint de Telemetria Pós-Consulta.

Endpoints:
  POST /api/telemetry/iot              — Ingestao IoT autenticada
  GET  /api/telemetry/iot/<patient_id> — Consultar série temporal de um paciente
  GET  /api/telemetry/followups/<patient_id> — Histórico de follow-ups CRM
  POST /api/telemetry/admin/schedule-now     — Trigger manual do agendamento diário
  POST /api/telemetry/admin/dispatch-now     — Trigger manual do envio de pendentes
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from src.web.routes.api_v1 import _require_json_csrf, api_role_required

logger = logging.getLogger("cannabia.routes.telemetry")

telemetry_bp = Blueprint("telemetry", __name__, url_prefix="/api/telemetry")


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _require_clinic_id():
    """Garante que clinic_id está no contexto (multi-tenant)."""
    clinic_id = getattr(g, "clinic_id", None)
    if not clinic_id:
        return None, (jsonify({"error": "clinic_id não resolvido."}), 403)
    return clinic_id, None


def _parse_iso(value: str) -> datetime:
    """Parse ISO 8601 com fallback para formatos comuns."""
    # Python 3.11+ aceita fromisoformat com Z
    value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def _serialize(value):
    """Serializa datetime/Decimal para JSON."""
    from decimal import Decimal
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _serialize_row(row: dict) -> dict:
    return {k: _serialize(v) for k, v in row.items()}


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/telemetry/iot — Ingestao IoT autenticada
# ═══════════════════════════════════════════════════════════════════════════════

@telemetry_bp.route("/iot", methods=["POST"])
@api_role_required("Admin", "AdminClinica", "Medico", "Recepcao")
def ingest_iot_data():
    """
    Recebe leituras de telemetria de dispositivos IoT/wearables.
    Requer sessao autenticada e CSRF; integracoes server-to-server devem usar
    um endpoint/token dedicado em sprint futura.

    Aceita um único reading ou batch (array).

    Body (single):
    {
        "patient_id": 42,
        "source": "apple_health",
        "metric_type": "sleep_hours",
        "value": 7.5,
        "unit": "hours",
        "recorded_at": "2026-04-02T23:30:00Z",
        "metadata": {"sleep_stage": "deep", "device": "Apple Watch S9"}
    }

    Body (batch):
    {
        "readings": [
            { ... },
            { ... }
        ]
    }

    Responses:
        201 — Leituras armazenadas com sucesso.
        202 — Batch aceito para processamento.
        400 — Payload inválido.
        403 — clinic_id não resolvido.
    """
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    clinic_id, err = _require_clinic_id()
    if err:
        return err

    if not request.is_json:
        return jsonify({"error": "Content-Type deve ser application/json."}), 400

    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Body JSON vazio ou inválido."}), 400

    from src.repositories.telemetry_repository import (
        insert_iot_reading,
        insert_iot_readings_batch,
    )

    # ── Batch mode ──
    if "readings" in body:
        readings_raw = body["readings"]
        if not isinstance(readings_raw, list) or len(readings_raw) == 0:
            return jsonify({"error": "'readings' deve ser uma lista não-vazia."}), 400

        if len(readings_raw) > 500:
            return jsonify({"error": "Máximo de 500 leituras por batch."}), 400

        readings = []
        errors = []
        for i, r in enumerate(readings_raw):
            try:
                readings.append(_validate_reading(clinic_id, r))
            except ValueError as exc:
                errors.append({"index": i, "error": str(exc)})

        if errors and not readings:
            return jsonify({"error": "Nenhuma leitura válida.", "details": errors}), 400

        ids = insert_iot_readings_batch(readings)

        response = {
            "status": "accepted",
            "stored": len(ids),
            "ids": ids,
        }
        if errors:
            response["warnings"] = errors

        return jsonify(response), 202

    # ── Single reading ──
    try:
        reading = _validate_reading(clinic_id, body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    reading_id = insert_iot_reading(**reading)

    return jsonify({
        "status": "stored",
        "id": reading_id,
        "metric_type": reading["metric_type"],
        "recorded_at": reading["recorded_at"].isoformat(),
    }), 201


def _validate_reading(clinic_id: int, data: dict) -> dict:
    """Valida e normaliza uma leitura IoT. Raises ValueError."""
    required = ("patient_id", "source", "metric_type", "value", "unit", "recorded_at")
    missing = [f for f in required if f not in data]
    if missing:
        raise ValueError(f"Campos obrigatórios ausentes: {', '.join(missing)}")

    allowed_sources = ("apple_health", "google_fit", "manual", "withings", "fitbit")
    if data["source"] not in allowed_sources:
        raise ValueError(
            f"source inválido: '{data['source']}'. "
            f"Permitidos: {', '.join(allowed_sources)}"
        )

    allowed_metrics = (
        "sleep_hours", "sleep_score", "heart_rate", "heart_rate_variability",
        "spo2", "steps", "pain_score", "anxiety_score", "mood_score",
        "blood_pressure_systolic", "blood_pressure_diastolic",
        "body_temperature", "respiratory_rate", "weight",
    )
    if data["metric_type"] not in allowed_metrics:
        raise ValueError(
            f"metric_type inválido: '{data['metric_type']}'. "
            f"Permitidos: {', '.join(allowed_metrics)}"
        )

    try:
        value = float(data["value"])
    except (TypeError, ValueError):
        raise ValueError(f"'value' deve ser numérico, recebido: {data['value']}")

    try:
        recorded_at = _parse_iso(data["recorded_at"])
    except (ValueError, TypeError):
        raise ValueError(
            f"'recorded_at' deve ser ISO 8601, recebido: {data['recorded_at']}"
        )

    return {
        "clinic_id": clinic_id,
        "patient_id": int(data["patient_id"]),
        "source": data["source"],
        "metric_type": data["metric_type"],
        "value": value,
        "unit": str(data["unit"]),
        "recorded_at": recorded_at,
        "metadata": data.get("metadata"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/telemetry/iot/<patient_id> — Consulta série temporal
# ═══════════════════════════════════════════════════════════════════════════════

@telemetry_bp.route("/iot/<int:patient_id>", methods=["GET"])
@api_role_required("Admin", "AdminClinica", "Medico", "Recepcao")
def query_patient_iot(patient_id: int):
    """
    Consulta leituras IoT de um paciente.

    Query params:
        metric_type (obrigatório) — ex: sleep_hours, heart_rate
        start       (obrigatório) — ISO 8601
        end         (obrigatório) — ISO 8601
        limit       (opcional)    — máximo de registros (default: 500)

    Response 200:
    {
        "patient_id": 42,
        "metric_type": "sleep_hours",
        "count": 15,
        "readings": [ { ... }, ... ]
    }
    """
    clinic_id, err = _require_clinic_id()
    if err:
        return err

    metric_type = request.args.get("metric_type")
    start_str = request.args.get("start")
    end_str = request.args.get("end")

    if not all([metric_type, start_str, end_str]):
        return jsonify({
            "error": "Parâmetros obrigatórios: metric_type, start, end",
        }), 400

    try:
        start = _parse_iso(start_str)
        end = _parse_iso(end_str)
    except ValueError:
        return jsonify({"error": "start/end devem ser ISO 8601."}), 400

    limit = min(int(request.args.get("limit", "500")), 1000)

    from src.repositories.telemetry_repository import query_iot_timeseries

    rows = query_iot_timeseries(
        clinic_id=clinic_id,
        patient_id=patient_id,
        metric_type=metric_type,
        start=start,
        end=end,
        limit=limit,
    )

    return jsonify({
        "patient_id": patient_id,
        "metric_type": metric_type,
        "count": len(rows),
        "readings": [_serialize_row(r) for r in rows],
    }), 200


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/telemetry/followups/<patient_id> — Histórico CRM
# ═══════════════════════════════════════════════════════════════════════════════

@telemetry_bp.route("/followups/<int:patient_id>", methods=["GET"])
@api_role_required("Admin", "AdminClinica", "Medico", "Recepcao")
def list_patient_followups(patient_id: int):
    """
    Lista follow-ups agendados/enviados/respondidos de um paciente.
    """
    clinic_id, err = _require_clinic_id()
    if err:
        return err

    from src.repositories.telemetry_repository import list_followups_for_patient

    rows = list_followups_for_patient(clinic_id=clinic_id, patient_id=patient_id)

    return jsonify({
        "patient_id": patient_id,
        "count": len(rows),
        "followups": [_serialize_row(r) for r in rows],
    }), 200


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/telemetry/admin/schedule-now — Trigger manual (admin)
# ═══════════════════════════════════════════════════════════════════════════════

@telemetry_bp.route("/admin/schedule-now", methods=["POST"])
@api_role_required("Admin", "AdminClinica")
def admin_schedule_now():
    """
    Trigger manual: agenda follow-ups para consultas de hoje.
    Admin-only.
    """
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    try:
        from src.infra.telemetry_tasks import enqueue_schedule_daily_followups
        job_id = enqueue_schedule_daily_followups()
        return jsonify({"status": "enqueued", "job_id": job_id}), 202
    except Exception as exc:
        logger.error("Falha ao enfileirar schedule_daily: %s", exc, exc_info=True)
        return jsonify({"error": str(exc)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/telemetry/admin/dispatch-now — Trigger manual (admin)
# ═══════════════════════════════════════════════════════════════════════════════

@telemetry_bp.route("/admin/dispatch-now", methods=["POST"])
@api_role_required("Admin", "AdminClinica")
def admin_dispatch_now():
    """
    Trigger manual: processa e envia follow-ups pendentes agora.
    Admin-only.
    """
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    try:
        from src.infra.telemetry_tasks import enqueue_dispatch_pending_followups
        job_id = enqueue_dispatch_pending_followups()
        return jsonify({"status": "enqueued", "job_id": job_id}), 202
    except Exception as exc:
        logger.error("Falha ao enfileirar dispatch: %s", exc, exc_info=True)
        return jsonify({"error": str(exc)}), 500
