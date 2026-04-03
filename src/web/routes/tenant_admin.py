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

tenant_admin_bp = Blueprint("tenant_admin", __name__, url_prefix="/api/v1/admin/tenants")


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


@tenant_admin_bp.post("/<int:tenant_id>/users")
@_admin_required
def invite_user(tenant_id: int):
    """
    POST /api/v1/admin/tenants/<id>/users

    Cria ou vincula um usuário ao tenant com a role especificada.

    Body JSON:
        username  (str, obrigatório) — Nome de usuário (único global)
        password  (str, obrigatório) — Senha (mín. 6 caracteres)
        role      (str, opcional)    — Role: Admin, Medico, Atendente (default: Medico)

    Resposta 201:
        { data: { user_id, tenant_id, clinic_id, username, role, is_new_user } }
    """
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
