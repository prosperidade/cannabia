# src/infra/permissions.py
"""
Framework de RBAC (Role-Based Access Control) com permissões granulares.

Arquitetura:
    - Permissões são strings no formato "recurso:ação" (ex: "attendance:read").
    - Roles mapeiam para conjuntos de permissões.
    - O decorator api_permission_required() verifica se o usuário possui
      pelo menos uma das permissões exigidas.
    - Mantém compatibilidade com api_role_required() existente — que
      internamente resolve para permissões.

Uso:
    from src.infra.permissions import api_permission_required

    @api_permission_required("attendance:read")
    def list_attendances():
        ...

    @api_permission_required("medical_record:write", "attendance:review")
    def review_attendance():
        ...
"""

from __future__ import annotations

from functools import wraps
from typing import FrozenSet

from flask import g, jsonify
from flask_login import current_user

from src.infra.security import get_effective_roles

# ═══════════════════════════════════════════════════════════════════════
# Registro de permissões granulares
# Formato: "recurso:ação"
# ═══════════════════════════════════════════════════════════════════════

# -- Sessão e autenticação
SESSION_READ = "session:read"
SESSION_WRITE = "session:write"

# -- Dashboard
DASHBOARD_READ = "dashboard:read"

# -- Mensagens
MESSAGE_READ = "message:read"

# -- Atendimentos / Anamneses
ATTENDANCE_READ = "attendance:read"
ATTENDANCE_REVIEW = "attendance:review"

# -- Prontuário médico
MEDICAL_RECORD_READ = "medical_record:read"
MEDICAL_RECORD_WRITE = "medical_record:write"

# -- Timeline do paciente
TIMELINE_READ = "timeline:read"

# -- Agendamentos
APPOINTMENT_READ = "appointment:read"
APPOINTMENT_WRITE = "appointment:write"

# -- Pipeline de IA
AI_EXECUTE = "ai:execute"
AI_METRICS_READ = "ai:metrics_read"

# -- Administração de sistema
ADMIN_METRICS = "admin:metrics"
ADMIN_USERS = "admin:users"
ADMIN_TENANTS = "admin:tenants"
ADMIN_KNOWLEDGE = "admin:knowledge"
ADMIN_PROMPTS = "admin:prompts"
ADMIN_AUDIT = "admin:audit"


# ═══════════════════════════════════════════════════════════════════════
# Mapeamento Role -> Permissões
#
# Cada role herda todas as permissões do nível inferior:
#   Recepcao/Atendente < Medico < Admin
# ═══════════════════════════════════════════════════════════════════════

_ATENDENTE_PERMISSIONS: FrozenSet[str] = frozenset({
    SESSION_READ,
    SESSION_WRITE,
    DASHBOARD_READ,
    MESSAGE_READ,
    ATTENDANCE_READ,
    APPOINTMENT_READ,
    APPOINTMENT_WRITE,
    TIMELINE_READ,
})

_MEDICO_PERMISSIONS: FrozenSet[str] = _ATENDENTE_PERMISSIONS | frozenset({
    ATTENDANCE_REVIEW,
    MEDICAL_RECORD_READ,
    MEDICAL_RECORD_WRITE,
    AI_EXECUTE,
    AI_METRICS_READ,
})

_ADMIN_PERMISSIONS: FrozenSet[str] = _MEDICO_PERMISSIONS | frozenset({
    ADMIN_METRICS,
    ADMIN_USERS,
    ADMIN_TENANTS,
    ADMIN_KNOWLEDGE,
    ADMIN_PROMPTS,
    ADMIN_AUDIT,
})

# Mapa role normalizado -> permissões
ROLE_PERMISSIONS: dict[str, FrozenSet[str]] = {
    "Admin": _ADMIN_PERMISSIONS,
    "Medico": _MEDICO_PERMISSIONS,
    "Recepcao": _ATENDENTE_PERMISSIONS,
    "Atendente": _ATENDENTE_PERMISSIONS,
}


def get_user_permissions() -> frozenset[str]:
    """
    Retorna o conjunto de permissões do usuário atual,
    baseado em todas as suas roles efetivas (global + tenant + clinic).
    """
    effective_roles = get_effective_roles()
    permissions: set[str] = set()
    for role in effective_roles:
        role_perms = ROLE_PERMISSIONS.get(role, frozenset())
        permissions.update(role_perms)
    return frozenset(permissions)


def has_permission(*required_permissions: str) -> bool:
    """
    Verifica se o usuário atual possui PELO MENOS UMA das permissões exigidas.
    Semântica OR — basta ter qualquer uma para ser autorizado.
    """
    user_perms = get_user_permissions()
    return bool(user_perms.intersection(required_permissions))


def has_all_permissions(*required_permissions: str) -> bool:
    """
    Verifica se o usuário atual possui TODAS as permissões exigidas.
    Semântica AND — precisa ter todas.
    """
    user_perms = get_user_permissions()
    return all(p in user_perms for p in required_permissions)


# ═══════════════════════════════════════════════════════════════════════
# Decorators para rotas da API
# ═══════════════════════════════════════════════════════════════════════

def _error_response(code: str, message: str, status: int):
    """Helper para respostas de erro no padrão do envelope da API v1."""
    return jsonify({
        "error": {
            "code": code,
            "message": message,
            "details": {},
        }
    }), status


def api_permission_required(*permissions: str):
    """
    Decorator que exige que o usuário autenticado possua pelo menos
    uma das permissões listadas (semântica OR).

    Uso:
        @api_permission_required("attendance:read")
        @api_permission_required("medical_record:write", "attendance:review")
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return _error_response(
                    "unauthenticated",
                    "Autenticação necessária.",
                    401,
                )

            if not has_permission(*permissions):
                return _error_response(
                    "forbidden",
                    "Sem permissão para acessar este recurso.",
                    403,
                )

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def api_all_permissions_required(*permissions: str):
    """
    Decorator que exige que o usuário possua TODAS as permissões listadas.
    Útil para operações que combinam múltiplas capacidades.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return _error_response(
                    "unauthenticated",
                    "Autenticação necessária.",
                    401,
                )

            if not has_all_permissions(*permissions):
                return _error_response(
                    "forbidden",
                    "Sem permissão para acessar este recurso.",
                    403,
                )

            return fn(*args, **kwargs)
        return wrapper
    return decorator
