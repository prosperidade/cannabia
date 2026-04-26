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
    # ── Super admin da plataforma (global, raro) ──
    # Apenas o time interno. Acessa /admin com tenants, knowledge global,
    # configuracao tecnica de agentes IA, auditoria global de gastos LLM.
    "admin": "Admin",
    "administrator": "Admin",
    "super_admin": "Admin",
    "platform_admin": "Admin",

    # ── Admin local de um tenant (clinica/associacao) ──
    # Combina com qualquer role principal via flag `is_clinic_admin`.
    # Quem tem esse role efetivo ve Operacao, Configuracoes, DNA,
    # Conformidade-gerir do *seu* tenant, mas nao knowledge global nem
    # listagem de tenants alheios.
    "adminclinica": "AdminClinica",
    "admin_clinica": "AdminClinica",
    "admin_clinic": "AdminClinica",
    "clinic_admin": "AdminClinica",
    "tenant_admin": "AdminClinica",
    "org_admin": "AdminClinica",
    "organization_admin": "AdminClinica",

    # ── Medico ──
    "medico": "Medico",
    "doctor": "Medico",
    "physician": "Medico",

    # ── Recepcao (era "Atendente" no schema antigo — migration 038) ──
    "recepcao": "Recepcao",
    "recepicao": "Recepcao",
    "recepcionista": "Recepcao",
    "atendente": "Recepcao",
    "agent": "Recepcao",
    "assistant": "Recepcao",
    "agente": "Recepcao",
    "agente_atendimento": "Recepcao",
    "agente_acompanhamento": "Recepcao",

    # ── Financeiro ──
    "financeiro": "Financeiro",
    "financial": "Financeiro",
    "finance": "Financeiro",

    # ── Paciente ──
    "paciente": "Paciente",
    "patient": "Paciente",
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
    """Retorna a lista de roles efetivos do usuario logado (canonicos).

    Coleta de 3 fontes:
      1. `current_user.role` (papel principal — `users.role`)
      2. `g.tenant_role` / `g.clinic_role` (papel no contexto do tenant)
      3. Flag `current_user.is_clinic_admin` — se True, adiciona
         "AdminClinica" aos roles efetivos. Permite que medico-dono
         (Medico+is_clinic_admin) seja autorizado em endpoints que
         pedem AdminClinica sem precisar de role secundario.
    """
    roles = []

    for role in (
        getattr(current_user, "role", None),
        getattr(g, "tenant_role", None),
        getattr(g, "clinic_role", None),
    ):
        normalized = normalize_role_name(role)
        if normalized and normalized not in roles:
            roles.append(normalized)

    if getattr(current_user, "is_clinic_admin", False):
        if "AdminClinica" not in roles:
            roles.append("AdminClinica")

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
