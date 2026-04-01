# src/infra/security.py
import logging
import re
from functools import wraps
from flask import abort, g
from flask_login import current_user, login_required

SENSITIVE_KEYS = {
    "authorization",
    "token",
    "verify_token",
    "meta_whatsapp_key",
    "email_password",
    "password",
    "secret",
}

ROLE_ALIASES = {
    "admin": "Admin",
    "administrator": "Admin",
    "clinic_admin": "Admin",
    "tenant_admin": "Admin",
    "super_admin": "Admin",
    "org_admin": "Admin",
    "organization_admin": "Admin",
    "medico": "Medico",
    "doctor": "Medico",
    "physician": "Medico",
    "atendente": "Atendente",
    "agent": "Atendente",
    "assistant": "Atendente",
    "agente": "Atendente",
    "agente_atendimento": "Atendente",
    "agente_acompanhamento": "Atendente",
}


def redact_text(value: str) -> str:
    if not value:
        return value
    value = re.sub(r"(Bearer\s+)[A-Za-z0-9._\-]+", r"\1***", value)
    value = re.sub(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})", r"***@\2", value)
    value = re.sub(r"\b\d{8,15}\b", "***PHONE***", value)
    return value


def redact_dict(data):
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if str(k).lower() in SENSITIVE_KEYS:
                out[k] = "***REDACTED***"
            else:
                out[k] = redact_dict(v)
        return out
    if isinstance(data, list):
        return [redact_dict(i) for i in data]
    if isinstance(data, str):
        return redact_text(data)
    return data


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        record.msg = redact_text(str(record.msg))
        if record.args:
            record.args = tuple(redact_text(str(a)) for a in record.args)
        return super().format(record)


def normalize_role_name(role):
    if role is None:
        return None

    raw = str(role).strip()
    if not raw:
        return None

    key = raw.lower().replace("-", "_").replace(" ", "_")
    return ROLE_ALIASES.get(key, raw)


def get_effective_roles():
    roles = []

    for role in (
        getattr(current_user, "role", None),
        getattr(g, "tenant_role", None),
        getattr(g, "clinic_role", None),
    ):
        normalized = normalize_role_name(role)
        if normalized and normalized not in roles:
            roles.append(normalized)

    return roles


def role_required(*allowed_roles: str):
    """
    Controle de acesso por role usando Flask-Login.
    Use assim:
        @role_required("Admin", "Medico")
    """
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)

            allowed = {
                normalized
                for normalized in (normalize_role_name(role) for role in allowed_roles)
                if normalized
            }
            effective_roles = get_effective_roles()

            if not effective_roles:
                abort(403, description="Usuário sem role definida.")

            if not allowed.intersection(effective_roles):
                abort(403, description="Sem permissão para acessar este recurso.")

            return fn(*args, **kwargs)

        return wrapper

    return decorator
