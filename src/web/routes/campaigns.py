# src/web/routes/campaigns.py
"""
Blueprint da API de Campanhas Ativas.

Endpoints REST para gerenciar templates, disparar execuções e
consultar status de campanhas. Escopado por clinic_id do contexto.

Todos os endpoints exigem autenticação e role Admin ou Medico.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from functools import wraps
from typing import Any, Optional

from flask import Blueprint, g, jsonify, request
from flask_login import current_user

from src.infra.security import get_effective_roles

campaigns_bp = Blueprint("campaigns", __name__, url_prefix="/api/v1/campaigns")


# ═══════════════════════════════════════════════════════════════════════════
# Helpers (espelham o padrão do api_v1)
# ═══════════════════════════════════════════════════════════════════════════

def _serialize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _success(data: Any, status: int = 200, meta: Optional[dict] = None):
    payload: dict[str, Any] = {"data": _serialize(data)}
    if meta:
        payload["meta"] = _serialize(meta)
    return jsonify(payload), status


def _error(code: str, message: str, status: int, details: Optional[dict] = None):
    return jsonify({
        "error": {"code": code, "message": message, "details": _serialize(details or {})}
    }), status


def _json_payload() -> dict:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _campaign_auth_required(fn):
    """Exige autenticação e role Admin ou Medico + clinic_id no contexto."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return _error("unauthenticated", "Autenticação necessária.", 401)

        effective = get_effective_roles()
        if not {"Admin", "Medico"}.intersection(effective):
            return _error("forbidden", "Sem permissão para gerenciar campanhas.", 403)

        if not getattr(g, "clinic_id", None):
            return _error("context_missing", "clinic_id não disponível no contexto.", 400)

        return fn(*args, **kwargs)
    return wrapper


@campaigns_bp.after_request
def apply_cors(response):
    from src.config import FRONTEND_ORIGINS
    origin = request.headers.get("Origin")
    if origin and origin in FRONTEND_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRF-Token"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Vary"] = "Origin"
    return response


# ═══════════════════════════════════════════════════════════════════════════
# Templates
# ═══════════════════════════════════════════════════════════════════════════

@campaigns_bp.post("/templates")
@_campaign_auth_required
def create_template():
    """
    POST /api/v1/campaigns/templates

    Cria um novo template de campanha.

    Body JSON:
        name           (str, obrigatório) — Nome do template
        template_body  (str, obrigatório) — Corpo com variáveis {{patient_name}}
        channel        (str, opcional)    — whatsapp, email, sms (default: whatsapp)
        description    (str, opcional)    — Descrição do template
    """
    from src.services.campaign_service import create_template as svc_create

    payload = _json_payload()
    name = (payload.get("name") or "").strip()
    template_body = (payload.get("template_body") or "").strip()
    channel = (payload.get("channel") or "whatsapp").strip()
    description = (payload.get("description") or "").strip() or None

    if not name or not template_body:
        return _error("validation_error", "name e template_body são obrigatórios.", 422)

    try:
        result = svc_create(
            tenant_id=getattr(g, "tenant_id", None) or g.clinic_id,
            clinic_id=g.clinic_id,
            name=name,
            template_body=template_body,
            channel=channel,
            description=description,
            created_by=int(current_user.id),
        )
        return _success(result, status=201)
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)


@campaigns_bp.get("/templates")
@_campaign_auth_required
def list_templates():
    """
    GET /api/v1/campaigns/templates?status=active&channel=whatsapp

    Lista templates de campanha da clínica.
    """
    from src.services.campaign_service import list_templates as svc_list

    status = (request.args.get("status") or "").strip() or None
    channel = (request.args.get("channel") or "").strip() or None

    try:
        limit = min(int(request.args.get("limit", 50)), 100)
    except (TypeError, ValueError):
        limit = 50

    results = svc_list(g.clinic_id, status=status, channel=channel, limit=limit)
    return _success(results, meta={"count": len(results)})


@campaigns_bp.get("/templates/<int:template_id>")
@_campaign_auth_required
def get_template(template_id: int):
    """
    GET /api/v1/campaigns/templates/<id>

    Retorna detalhes de um template.
    """
    from src.services.campaign_service import get_template as svc_get

    template = svc_get(template_id, g.clinic_id)
    if not template:
        return _error("not_found", "Template não encontrado.", 404)
    return _success(template)


@campaigns_bp.patch("/templates/<int:template_id>/status")
@_campaign_auth_required
def update_template_status(template_id: int):
    """
    PATCH /api/v1/campaigns/templates/<id>/status

    Ativa ou arquiva um template.

    Body JSON:
        status  (str, obrigatório) — draft, active, archived
    """
    from src.services.campaign_service import update_template_status as svc_update

    payload = _json_payload()
    status = (payload.get("status") or "").strip()

    if not status:
        return _error("validation_error", "status é obrigatório.", 422)

    try:
        result = svc_update(template_id, g.clinic_id, status)
        return _success(result)
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)


# ═══════════════════════════════════════════════════════════════════════════
# Execuções (Disparos)
# ═══════════════════════════════════════════════════════════════════════════

@campaigns_bp.post("/templates/<int:template_id>/send")
@_campaign_auth_required
def send_campaign(template_id: int):
    """
    POST /api/v1/campaigns/templates/<id>/send

    Dispara uma campanha para processamento assíncrono.

    Body JSON (opcional):
        patient_ids  (list[int], opcional) — IDs dos pacientes alvo.
                                             Se omitido, envia para todos com
                                             endereço válido no canal do template.
    """
    from src.services.campaign_service import enqueue_campaign

    payload = _json_payload()
    patient_ids = payload.get("patient_ids")

    if patient_ids is not None and not isinstance(patient_ids, list):
        return _error("validation_error", "patient_ids deve ser uma lista de inteiros.", 422)

    try:
        result = enqueue_campaign(
            template_id=template_id,
            clinic_id=g.clinic_id,
            triggered_by=int(current_user.id),
            patient_ids=patient_ids,
        )
        return _success(result, status=202)
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)


@campaigns_bp.get("/executions")
@_campaign_auth_required
def list_executions():
    """
    GET /api/v1/campaigns/executions?template_id=1&status=completed

    Lista execuções de campanha da clínica.
    """
    from src.services.campaign_service import list_executions as svc_list

    template_id = request.args.get("template_id", type=int)
    status = (request.args.get("status") or "").strip() or None

    try:
        limit = min(int(request.args.get("limit", 20)), 100)
    except (TypeError, ValueError):
        limit = 20

    results = svc_list(g.clinic_id, template_id=template_id, status=status, limit=limit)
    return _success(results, meta={"count": len(results)})


@campaigns_bp.get("/executions/<int:execution_id>")
@_campaign_auth_required
def get_execution(execution_id: int):
    """
    GET /api/v1/campaigns/executions/<id>

    Retorna status detalhado de uma execução de campanha.
    """
    from src.services.campaign_service import get_execution_status

    execution = get_execution_status(execution_id, g.clinic_id)
    if not execution:
        return _error("not_found", "Execução não encontrada.", 404)
    return _success(execution)
