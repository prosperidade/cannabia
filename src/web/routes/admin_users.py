# src/web/routes/admin_users.py
"""
Admin user management API endpoints.
Prefix: /api/v1/admin/users
"""

from __future__ import annotations

import logging

import bcrypt
from flask import Blueprint, g, request
from flask_login import current_user
from psycopg2 import OperationalError

from src.infra.database import db_cursor
from src.web.routes.api_v1 import (
    _error,
    _json_payload,
    _paginate,
    _pagination_args,
    _require_json_csrf,
    _success,
    api_role_required,
)

logger = logging.getLogger("cannabia.admin_users")

admin_users_bp = Blueprint("admin_users", __name__, url_prefix="/api/v1/admin/users")


def _hash_password(password: str) -> str:
    """Hash a password using bcrypt (same scheme as user_repository)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


@admin_users_bp.get("/")
@api_role_required("Admin")
def list_users():
    """List all users with their clinic memberships."""
    page, page_size = _pagination_args()
    search = (request.args.get("search") or "").strip()
    role_filter = (request.args.get("role") or "").strip()

    try:
        with db_cursor(dictionary=True) as (_, cursor):
            where_clauses = ["1=1"]
            params: list = []

            if search:
                where_clauses.append("(u.username ILIKE %s OR u.full_name ILIKE %s OR u.email ILIKE %s)")
                like = f"%{search}%"
                params.extend([like, like, like])

            if role_filter:
                where_clauses.append("u.role = %s")
                params.append(role_filter)

            where_sql = " AND ".join(where_clauses)

            cursor.execute(
                f"""
                SELECT u.id, u.username, u.full_name, u.email, u.role,
                       u.is_active, u.created_at, u.updated_at,
                       COALESCE(
                           json_agg(
                               json_build_object(
                                   'clinic_id', uc.clinic_id,
                                   'clinic_name', c.name,
                                   'clinic_role', uc.role
                               )
                           ) FILTER (WHERE uc.clinic_id IS NOT NULL),
                           '[]'
                       ) AS clinics
                FROM users u
                LEFT JOIN user_clinics uc ON uc.user_id = u.id
                LEFT JOIN clinics c ON c.id = uc.clinic_id
                WHERE {where_sql}
                GROUP BY u.id
                ORDER BY u.created_at DESC
                """,
                tuple(params),
            )
            rows = cursor.fetchall()
            items, meta = _paginate(rows, page, page_size)
            return _success(items, meta=meta)
    except OperationalError:
        logger.error("DB unavailable on admin_users.list_users", exc_info=True)
        return _error("database_unavailable", "Servico temporariamente indisponivel.", 503)
    except Exception:
        logger.error("Unexpected error on admin_users.list_users", exc_info=True)
        return _error("internal_error", "Erro interno ao processar requisicao.", 500)


@admin_users_bp.post("/")
@api_role_required("Admin")
def create_user():
    """Create a new user."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    username = (payload.get("username") or "").strip()
    password = (payload.get("password") or "").strip()
    role = (payload.get("role") or "Atendente").strip()
    full_name = (payload.get("full_name") or "").strip()
    email = (payload.get("email") or "").strip()
    clinic_id = payload.get("clinic_id")

    if not username or not password:
        return _error("validation_error", "username e password sao obrigatorios.", 422)

    if len(password) < 6:
        return _error("validation_error", "password deve ter no minimo 6 caracteres.", 422)

    valid_roles = ("Admin", "Medico", "Atendente", "Paciente")
    if role not in valid_roles:
        return _error("validation_error", f"role deve ser um de: {', '.join(valid_roles)}", 422)

    try:
        with db_cursor(dictionary=True) as (conn, cursor):
            # Check duplicate
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                return _error("conflict", "Username ja existe.", 409)

            password_hash = _hash_password(password)

            cursor.execute(
                """
                INSERT INTO users (username, password_hash, role, full_name, email, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                RETURNING id, created_at
                """,
                (username, password_hash, role, full_name or None, email or None),
            )
            user = cursor.fetchone()

            # Link to clinic if provided
            target_clinic = clinic_id or getattr(g, "clinic_id", None)
            if target_clinic:
                cursor.execute(
                    """
                    INSERT INTO user_clinics (user_id, clinic_id, role, is_default, created_at)
                    VALUES (%s, %s, %s, TRUE, NOW())
                    ON CONFLICT DO NOTHING
                    """,
                    (user["id"], target_clinic, role),
                )

            conn.commit()
            return _success({"id": user["id"], "created_at": user["created_at"]}, status=201)
    except Exception:
        logger.error("Failed to create user", exc_info=True)
        return _error("internal_error", "Falha ao criar usuario.", 500)


@admin_users_bp.patch("/<int:user_id>")
@api_role_required("Admin")
def update_user(user_id: int):
    """Update user fields (role, active status, etc)."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()

    updates = []
    params: list = []

    if "role" in payload:
        valid_roles = ("Admin", "Medico", "Atendente", "Paciente")
        if payload["role"] not in valid_roles:
            return _error("validation_error", f"role deve ser um de: {', '.join(valid_roles)}", 422)
        updates.append("role = %s")
        params.append(payload["role"])

    if "is_active" in payload:
        updates.append("is_active = %s")
        params.append(bool(payload["is_active"]))

    if "full_name" in payload:
        updates.append("full_name = %s")
        params.append(payload["full_name"])

    if "email" in payload:
        updates.append("email = %s")
        params.append(payload["email"])

    if not updates:
        return _error("validation_error", "Nenhum campo para atualizar.", 422)

    updates.append("updated_at = NOW()")
    params.append(user_id)

    try:
        with db_cursor(dictionary=True) as (conn, cursor):
            cursor.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = %s RETURNING id, username, role, is_active",
                tuple(params),
            )
            row = cursor.fetchone()
            if not row:
                return _error("not_found", "Usuario nao encontrado.", 404)
            conn.commit()
            return _success(row)
    except Exception:
        logger.error("Failed to update user", exc_info=True)
        return _error("internal_error", "Falha ao atualizar usuario.", 500)
