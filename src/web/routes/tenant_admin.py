# src/web/routes/tenant_admin.py
"""
Blueprint de administração de Tenants (B2B Onboarding).

Endpoints REST para criar, listar, atualizar tenants e convidar usuários.
Todos os endpoints exigem autenticação e role Admin.

Padrão de resposta: envelope { data, meta?, error? } consistente com api_v1.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from functools import wraps
from typing import Any, Optional

from flask import Blueprint, g, jsonify, request
from flask_login import current_user

from src.infra.security import get_effective_roles, normalize_role_name
from src.web.routes.auth import validate_csrf_value

tenant_admin_bp = Blueprint("tenant_admin", __name__, url_prefix="/api/v1/admin/tenants")

_MASKED_SECRET_VALUES = {"***", "********"}
_SECRET_FIELDS = {
    "meta_whatsapp_key",
    "whatsapp_app_secret",
    "verify_token",
    "email_password",
    "ai_api_key",
    "openai_api_key",
}


def _require_csrf():
    """Valida CSRF via header X-CSRF-Token ou body csrf_token."""
    payload = request.get_json(silent=True) or {}
    sent = request.headers.get("X-CSRF-Token") or (
        payload.get("csrf_token") if isinstance(payload, dict) else None
    ) or ""
    if not validate_csrf_value(sent):
        return _error("csrf_invalid", "CSRF invalido.", 400)
    return None


def _secret_update(payload: dict[str, Any], field: str) -> Any:
    value = payload.get(field)
    if value in _MASKED_SECRET_VALUES:
        return None
    return value


# ═══════════════════════════════════════════════════════════════════════════
# Helpers de serialização e resposta (espelham o padrão do api_v1)
# ═══════════════════════════════════════════════════════════════════════════

def _serialize(value: Any) -> Any:
    """Serializa tipos Python para JSON-safe."""
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
    if meta is not None:
        payload["meta"] = _serialize(meta)
    return jsonify(payload), status


def _error(code: str, message: str, status: int, details: Optional[dict] = None):
    return jsonify({
        "error": {
            "code": code,
            "message": message,
            "details": _serialize(details or {}),
        }
    }), status


def _json_payload() -> dict:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


# ═══════════════════════════════════════════════════════════════════════════
# Decorators de autenticação e autorização
# ═══════════════════════════════════════════════════════════════════════════

def _admin_required(fn):
    """Exige autenticação e role Admin para acesso ao endpoint."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return _error("unauthenticated", "Autenticação necessária.", 401)

        effective_roles = get_effective_roles()
        if "Admin" not in effective_roles:
            return _error("forbidden", "Apenas administradores podem gerenciar tenants.", 403)

        return fn(*args, **kwargs)
    return wrapper


# ═══════════════════════════════════════════════════════════════════════════
# CORS (espelha comportamento do api_v1_bp)
# ═══════════════════════════════════════════════════════════════════════════

@tenant_admin_bp.after_request
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
# Endpoints
# ═══════════════════════════════════════════════════════════════════════════

@tenant_admin_bp.post("")
@_admin_required
def create_tenant():
    """
    POST /api/v1/admin/tenants

    Cria um novo tenant com provisão completa (clinic, branding, integrations).

    Body JSON:
        legal_name       (str, obrigatório) — Razão social
        display_name     (str, obrigatório) — Nome de exibição
        tenant_type      (str, opcional)    — Tipo: clinic, association, doctor (default: clinic)
        slug             (str, opcional)    — Slug customizado (gerado se omitido)

    Resposta 201:
        { data: { tenant_id, clinic_id, slug, legal_name, display_name, tenant_type, status } }
    """
    csrf_error = _require_csrf()
    if csrf_error:
        return csrf_error

    from src.services.tenant_service import create_tenant as svc_create

    payload = _json_payload()
    legal_name = (payload.get("legal_name") or "").strip()
    display_name = (payload.get("display_name") or "").strip()
    tenant_type = (payload.get("tenant_type") or "clinic").strip()
    custom_slug = (payload.get("slug") or "").strip() or None

    if not legal_name or not display_name:
        return _error(
            "validation_error",
            "legal_name e display_name são obrigatórios.",
            422,
        )

    try:
        result = svc_create(
            legal_name=legal_name,
            display_name=display_name,
            tenant_type_slug=tenant_type,
            custom_slug=custom_slug,
        )
        return _success(result, status=201)
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)


@tenant_admin_bp.get("")
@_admin_required
def list_tenants():
    """
    GET /api/v1/admin/tenants?status=active&type=clinic&limit=50&offset=0

    Lista tenants com filtros opcionais.

    Query params:
        status  (str, opcional)  — Filtra por status (active, inactive, suspended)
        type    (str, opcional)  — Filtra por tipo de tenant
        limit   (int, opcional)  — Máximo de resultados (default 50, max 100)
        offset  (int, opcional)  — Offset para paginação (default 0)
    """
    from src.services.tenant_service import list_tenants as svc_list

    status = (request.args.get("status") or "").strip() or None
    tenant_type = (request.args.get("type") or "").strip() or None

    try:
        limit = min(int(request.args.get("limit", 50)), 100)
    except (TypeError, ValueError):
        limit = 50

    try:
        offset = max(int(request.args.get("offset", 0)), 0)
    except (TypeError, ValueError):
        offset = 0

    results = svc_list(status=status, tenant_type=tenant_type, limit=limit, offset=offset)
    return _success(results, meta={"limit": limit, "offset": offset, "count": len(results)})


@tenant_admin_bp.get("/<int:tenant_id>")
@_admin_required
def get_tenant(tenant_id: int):
    """
    GET /api/v1/admin/tenants/<id>

    Retorna detalhes completos de um tenant, incluindo branding e contagem de usuários.
    """
    from src.services.tenant_service import get_tenant_detail

    tenant = get_tenant_detail(tenant_id)
    if not tenant:
        return _error("not_found", "Tenant não encontrado.", 404)
    return _success(tenant)


@tenant_admin_bp.put("/<int:tenant_id>")
@_admin_required
def update_tenant(tenant_id: int):
    """
    PUT /api/v1/admin/tenants/<id>

    Atualiza campos editáveis de um tenant.

    Body JSON (todos opcionais — pelo menos um obrigatório):
        legal_name    (str) — Razão social
        display_name  (str) — Nome de exibição
        status        (str) — Status: active, inactive, suspended
    """
    csrf_error = _require_csrf()
    if csrf_error:
        return csrf_error

    from src.services.tenant_service import update_tenant as svc_update

    payload = _json_payload()
    try:
        result = svc_update(
            tenant_id,
            legal_name=payload.get("legal_name"),
            display_name=payload.get("display_name"),
            status=payload.get("status"),
        )
        return _success(result)
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)


@tenant_admin_bp.get("/<int:tenant_id>/branding")
@_admin_required
def get_tenant_branding(tenant_id: int):
    """GET /api/v1/admin/tenants/<id>/branding — retorna branding do tenant."""
    from src.repositories.tenant_settings_repository import get_branding

    branding = get_branding(tenant_id)
    if not branding:
        return _success({"tenant_id": tenant_id, "brand_name": None})
    return _success(branding)


@tenant_admin_bp.put("/<int:tenant_id>/branding")
@_admin_required
def update_tenant_branding(tenant_id: int):
    """
    PUT /api/v1/admin/tenants/<id>/branding

    Body JSON (opcionais):
        brand_name       (str)
        logo_url         (str)
        primary_color    (str — hex)
        secondary_color  (str — hex)
        subdomain        (str)
    """
    csrf_error = _require_csrf()
    if csrf_error:
        return csrf_error

    from src.repositories.tenant_settings_repository import upsert_branding

    payload = _json_payload()
    try:
        result = upsert_branding(
            tenant_id,
            brand_name=payload.get("brand_name"),
            logo_url=payload.get("logo_url"),
            primary_color=payload.get("primary_color"),
            secondary_color=payload.get("secondary_color"),
            subdomain=payload.get("subdomain"),
        )
        from src.infra.audit import log_audit_event
        log_audit_event(
            action="tenant_branding_updated",
            resource_type="tenant_branding",
            resource_id=str(tenant_id),
            details={"fields": sorted(k for k in payload.keys() if payload.get(k) is not None)},
        )
        return _success(result)
    except Exception as exc:
        return _error("validation_error", str(exc), 422)


@tenant_admin_bp.get("/<int:tenant_id>/integrations")
@_admin_required
def get_tenant_integrations(tenant_id: int):
    """
    GET /api/v1/admin/tenants/<id>/integrations

    Retorna configuracoes de integracao com segredos MASCARADOS.
    """
    from src.repositories.tenant_settings_repository import get_integrations

    integ = get_integrations(tenant_id, decrypted=False)
    if not integ:
        return _success({"tenant_id": tenant_id})
    return _success(integ)


@tenant_admin_bp.put("/<int:tenant_id>/integrations")
@_admin_required
def update_tenant_integrations(tenant_id: int):
    """
    PUT /api/v1/admin/tenants/<id>/integrations

    Body JSON (opcionais; segredos passam por criptografia):
        whatsapp_phone_number_id       (str)
        whatsapp_business_account_id   (str)
        meta_whatsapp_key              (str)
        whatsapp_app_secret            (str)
        verify_token                   (str)
        email_from                     (str)
        smtp_server                    (str)
        smtp_port                      (int)
        email_password                 (str)
        doctor_email                   (str)
        ai_provider                    (str: gemini|openai)
        ai_api_key                     (str)
        openai_api_key                 (str)
    """
    csrf_error = _require_csrf()
    if csrf_error:
        return csrf_error

    from src.repositories.tenant_settings_repository import upsert_integrations

    payload = _json_payload()
    try:
        smtp_port = payload.get("smtp_port")
        if smtp_port is not None and smtp_port != "":
            smtp_port = int(smtp_port)
        else:
            smtp_port = None

        result = upsert_integrations(
            tenant_id,
            whatsapp_phone_number_id=payload.get("whatsapp_phone_number_id"),
            whatsapp_business_account_id=payload.get("whatsapp_business_account_id"),
            meta_whatsapp_key=_secret_update(payload, "meta_whatsapp_key"),
            whatsapp_app_secret=_secret_update(payload, "whatsapp_app_secret"),
            verify_token=_secret_update(payload, "verify_token"),
            email_from=payload.get("email_from"),
            smtp_server=payload.get("smtp_server"),
            smtp_port=smtp_port,
            email_password=_secret_update(payload, "email_password"),
            doctor_email=payload.get("doctor_email"),
            ai_provider=payload.get("ai_provider"),
            ai_api_key=_secret_update(payload, "ai_api_key"),
            openai_api_key=_secret_update(payload, "openai_api_key"),
        )
        from src.infra.audit import log_audit_event
        log_audit_event(
            action="tenant_integrations_updated",
            resource_type="tenant_integrations",
            resource_id=str(tenant_id),
            details={
                "fields": sorted(
                    k for k in payload.keys()
                    if payload.get(k) not in (None, "")
                    and not (k in _SECRET_FIELDS and payload.get(k) in _MASKED_SECRET_VALUES)
                )
            },
        )
        return _success(result)
    except (TypeError, ValueError) as exc:
        return _error("validation_error", str(exc), 422)


@tenant_admin_bp.get("/<int:tenant_id>/plan")
@_admin_required
def get_tenant_plan(tenant_id: int):
    """GET /api/v1/admin/tenants/<id>/plan — retorna plano e quotas do tenant."""
    from src.repositories.tenant_settings_repository import get_tenant_quota

    plan = get_tenant_quota(tenant_id)
    if not plan:
        return _error("not_found", "Tenant nao encontrado.", 404)
    return _success(plan)


@tenant_admin_bp.put("/<int:tenant_id>/plan")
@_admin_required
def update_tenant_plan(tenant_id: int):
    """
    PUT /api/v1/admin/tenants/<id>/plan

    Body JSON (opcionais):
        billing_plan    (str: starter|professional|enterprise)
        ai_limit_month  (int)
        user_limit      (int)
    """
    csrf_error = _require_csrf()
    if csrf_error:
        return csrf_error

    from src.repositories.tenant_settings_repository import update_tenant_plan as repo_update

    payload = _json_payload()
    plan = payload.get("billing_plan")
    if plan and plan not in {"starter", "professional", "enterprise"}:
        return _error("validation_error", "billing_plan invalido.", 422)

    try:
        result = repo_update(
            tenant_id,
            billing_plan=plan,
            ai_limit_month=payload.get("ai_limit_month"),
            user_limit=payload.get("user_limit"),
        )
        from src.infra.audit import log_audit_event
        log_audit_event(
            action="tenant_plan_updated",
            resource_type="tenants",
            resource_id=str(tenant_id),
            details={"billing_plan": plan, "ai_limit_month": payload.get("ai_limit_month")},
        )
        return _success(result)
    except (TypeError, ValueError) as exc:
        return _error("validation_error", str(exc), 422)


@tenant_admin_bp.post("/<int:tenant_id>/users")
@_admin_required
def invite_user(tenant_id: int):
    """
    POST /api/v1/admin/tenants/<id>/users

    Cria ou vincula um usuário ao tenant com a role especificada.

    Body JSON:
        username  (str, obrigatório) — Nome de usuário (único global)
        password  (str, obrigatório) — Senha (mín. 6 caracteres)
        role      (str, opcional)    — Role: Admin, AdminClinica, Medico, Recepcao, Financeiro (default: Medico)

    Resposta 201:
        { data: { user_id, tenant_id, clinic_id, username, role, is_new_user } }
    """
    csrf_error = _require_csrf()
    if csrf_error:
        return csrf_error

    from src.services.tenant_service import invite_user_to_tenant

    payload = _json_payload()
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    role = (payload.get("role") or "Medico").strip()

    if not username or not password:
        return _error(
            "validation_error",
            "username e password são obrigatórios.",
            422,
        )

    try:
        result = invite_user_to_tenant(
            tenant_id=tenant_id,
            username=username,
            password=password,
            role=role,
        )
        return _success(result, status=201)
    except ValueError as exc:
        return _error("validation_error", str(exc), 422)
