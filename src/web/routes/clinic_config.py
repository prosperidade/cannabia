# src/web/routes/clinic_config.py
"""
Clinic configuration API.
Prefix: /api/v1/org
"""
from __future__ import annotations
import logging
from flask import Blueprint, g, request
from flask_login import current_user
from src.infra.database import db_cursor
from src.web.routes.api_v1 import (
    _error, _json_payload, _require_json_csrf, _success,
    api_role_required,
)

logger = logging.getLogger("cannabia.clinic_config")
clinic_config_bp = Blueprint("clinic_config", __name__, url_prefix="/api/v1/org")


@clinic_config_bp.get("/config")
@api_role_required("Admin", "Medico", "Atendente")
def get_clinic_config():
    """Return clinic configuration."""
    try:
        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                "SELECT id, name, slug, is_active, created_at FROM clinics WHERE id = %s",
                (g.clinic_id,),
            )
            clinic = cursor.fetchone()
            if not clinic:
                return _error("not_found", "Clinica nao encontrada.", 404)

            # Get branding if exists
            cursor.execute(
                """SELECT brand_name, logo_url, primary_color, secondary_color, subdomain
                   FROM tenant_branding WHERE tenant_id = (
                       SELECT id FROM tenants WHERE legacy_clinic_id = %s LIMIT 1
                   )""",
                (g.clinic_id,),
            )
            branding = cursor.fetchone() or {}

            return _success({
                "clinic": clinic,
                "branding": branding,
            })
    except Exception:
        logger.error("Error fetching clinic config", exc_info=True)
        return _success({"clinic": {"id": g.clinic_id, "name": "Clinica"}, "branding": {}})


@clinic_config_bp.patch("/config")
@api_role_required("Admin")
def update_clinic_config():
    """Update clinic configuration."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    updates = []
    params = []

    if "name" in payload:
        updates.append("name = %s")
        params.append(payload["name"])

    if not updates:
        return _error("validation_error", "Nenhum campo para atualizar.", 422)

    params.append(g.clinic_id)

    try:
        with db_cursor(dictionary=True) as (conn, cursor):
            cursor.execute(
                f"UPDATE clinics SET {', '.join(updates)} WHERE id = %s RETURNING id, name",
                tuple(params),
            )
            row = cursor.fetchone()
            conn.commit()
            return _success(row)
    except Exception:
        logger.error("Error updating clinic config", exc_info=True)
        return _error("internal_error", "Falha ao atualizar configuracao.", 500)
