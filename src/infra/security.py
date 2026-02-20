# src/infra/security.py
import logging
import re
from functools import wraps
from flask import abort
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

            role = getattr(current_user, "role", None)
            if role is None:
                abort(403, description="Usuário sem role definida.")

            if role not in allowed_roles:
                abort(403, description="Sem permissão para acessar este recurso.")

            return fn(*args, **kwargs)

        return wrapper

    return decorator
