# src/web/routes/clinic_config.py
"""
Clinic configuration API — backing da tela /org/configuracoes.

Le e grava configuracoes em 3 fontes:
  1. clinics.name                   — razao social
  2. tenant_branding (linha 1:1)    — identidade visual (logo, cores, subdomain, brand_name)
  3. tenant_settings.settings JSONB — todo o resto (cadastro, operacional,
                                       integracoes, dna, notificacoes)

GET retorna shape achatado (todos os campos no nivel raiz) que o frontend
ja espera. PATCH aceita o mesmo shape e distribui entre as 3 tabelas.

Permissoes:
  - GET: usuarios autenticados que pertencem ao tenant (todos os roles).
         Recepcao tambem precisa visualizar (ex.: numero do WhatsApp para
         responder mensagens).
  - PATCH: somente Admin (super) ou usuarios com is_clinic_admin=True.
           AdminClinica edita o seu proprio tenant.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from flask import Blueprint, g
from flask_login import current_user

from src.infra.database import db_cursor
from src.repositories.tenant_settings_repository import get_integrations, upsert_integrations
from src.web.routes.api_v1 import (
    _error,
    _json_payload,
    _require_json_csrf,
    _success,
    api_role_required,
)

logger = logging.getLogger("cannabia.clinic_config")
clinic_config_bp = Blueprint("clinic_config", __name__, url_prefix="/api/v1/org")

_MASKED_SECRET = "********"


# ---------------------------------------------------------------------------
# Mapeamento camelCase (UI) <-> coluna do tenant_branding
# ---------------------------------------------------------------------------

_BRANDING_FIELDS_UI_TO_DB: dict[str, str] = {
    "brandName":      "brand_name",
    "logoUrl":        "logo_url",
    "primaryColor":   "primary_color",
    "accentColor":    "secondary_color",  # UI chama de "accent", DB de "secondary"
    "subdomain":      "subdomain",
}

# Categorias do JSONB — apenas para validar o shape e organizar a leitura.
# Cada categoria e um dict com chaves arbitrarias (camelCase).
_SETTINGS_CATEGORIES: tuple[str, ...] = (
    "cadastro",
    "operacional",
    "integracoes",
    "businessDna",
    "notificacoes",
)

# Mapeamento camelCase do payload UI -> categoria onde gravar no JSONB.
# Campos que nao estao aqui sao ignorados (defesa contra campos extras).
_FIELD_TO_CATEGORY: dict[str, str] = {
    # cadastro
    "cnpj": "cadastro",
    "address": "cadastro",
    "phone": "cadastro",
    "email": "cadastro",
    # operacional
    "weekdayOpen": "operacional",
    "weekdayClose": "operacional",
    "weekendOpen": "operacional",
    "weekendClose": "operacional",
    "sundayClosed": "operacional",
    "consultationPrice": "operacional",
    "consultationDuration": "operacional",
    "modalityPresencial": "operacional",
    "modalityOnline": "operacional",
    # integracoes
    "whatsappNumber": "integracoes",
    "smtpHost": "integracoes",
    "smtpUser": "integracoes",
    # business dna
    "businessMission": "businessDna",
    "targetPatientProfile": "businessDna",
    "agentToneOfVoice": "businessDna",
    "internalPolicies": "businessDna",
    # notificacoes
    "notifyEmailNewPatient": "notificacoes",
    "notifyEmailAppointment": "notificacoes",
    "notifyEmailBilling": "notificacoes",
    "notifyWhatsappReminder": "notificacoes",
    "notifyWhatsappFollowup": "notificacoes",
    "notifyWhatsappBilling": "notificacoes",
}

_SECRET_FIELD_TO_INTEGRATION: dict[str, str] = {
    "apiKeyMeta": "meta_whatsapp_key",
    "apiKeyOpenAI": "openai_api_key",
    "apiKeyGemini": "ai_api_key",
    "smtpPassword": "email_password",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_tenant_id() -> int | None:
    """Retorna o tenant_id ativo do request (g.tenant_id ou via clinics)."""
    tenant_id = getattr(g, "tenant_id", None)
    if tenant_id is not None:
        return int(tenant_id)
    clinic_id = getattr(g, "clinic_id", None)
    if clinic_id is None:
        return None
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(
            "SELECT tenant_id FROM clinics WHERE id = %s", (clinic_id,)
        )
        row = cur.fetchone()
        return row["tenant_id"] if row and row.get("tenant_id") else None


def _user_can_edit() -> bool:
    """PATCH e permitido para Admin global ou is_clinic_admin=True."""
    if not current_user.is_authenticated:
        return False
    role = getattr(current_user, "role", None)
    if role == "Admin":
        return True
    return bool(getattr(current_user, "is_clinic_admin", False))


def _flatten_payload(
    clinic_row: dict[str, Any],
    branding_row: dict[str, Any] | None,
    settings_obj: dict[str, Any] | None,
) -> dict[str, Any]:
    """Monta o shape achatado que o frontend espera."""
    out: dict[str, Any] = {
        "name": clinic_row.get("name") or "",
    }

    # Branding — converte snake_case -> camelCase do UI.
    branding = branding_row or {}
    for ui_field, db_field in _BRANDING_FIELDS_UI_TO_DB.items():
        out[ui_field] = branding.get(db_field) or ""

    # Settings JSONB — flatten das categorias.
    settings_obj = settings_obj or {}
    for category in _SETTINGS_CATEGORIES:
        cat_data = settings_obj.get(category) or {}
        if isinstance(cat_data, dict):
            for k, v in cat_data.items():
                if k in _SECRET_FIELD_TO_INTEGRATION:
                    continue
                # Nao sobrescreve chaves ja preenchidas (ex.: name).
                if k not in out:
                    out[k] = v

    return out


def _masked_secret_fields(
    tenant_id: int,
    settings_obj: dict[str, Any] | None,
) -> dict[str, str]:
    out = {field: "" for field in _SECRET_FIELD_TO_INTEGRATION}
    legacy_integrations = {}
    if isinstance(settings_obj, dict):
        maybe_integrations = settings_obj.get("integracoes")
        if isinstance(maybe_integrations, dict):
            legacy_integrations = maybe_integrations

    for field in _SECRET_FIELD_TO_INTEGRATION:
        if legacy_integrations.get(field):
            out[field] = _MASKED_SECRET

    try:
        encrypted_integrations = get_integrations(tenant_id, decrypted=False) or {}
    except Exception:
        logger.warning("Falha ao carregar tenant_integrations mascarado", exc_info=True)
        encrypted_integrations = {}

    for ui_field, integration_field in _SECRET_FIELD_TO_INTEGRATION.items():
        if encrypted_integrations.get(integration_field):
            out[ui_field] = _MASKED_SECRET

    return out


def _split_secret_payload(payload: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for ui_field, integration_field in _SECRET_FIELD_TO_INTEGRATION.items():
        if ui_field not in payload:
            continue
        value = payload.get(ui_field)
        if value is None or value == _MASKED_SECRET:
            continue
        updates[integration_field] = str(value)
    return updates


def _legacy_secret_updates(settings_obj: dict[str, Any]) -> dict[str, Any]:
    integrations = settings_obj.get("integracoes")
    if not isinstance(integrations, dict):
        return {}

    updates: dict[str, Any] = {}
    for ui_field, integration_field in _SECRET_FIELD_TO_INTEGRATION.items():
        value = integrations.get(ui_field)
        if value not in (None, ""):
            updates[integration_field] = str(value)
    return updates


def _scrub_legacy_secret_settings(settings_obj: dict[str, Any]) -> bool:
    integrations = settings_obj.get("integracoes")
    if not isinstance(integrations, dict):
        return False

    changed = False
    for field in _SECRET_FIELD_TO_INTEGRATION:
        if field in integrations:
            integrations.pop(field, None)
            changed = True
    return changed


def _split_payload(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    """
    Distribui o payload achatado em:
      - clinics_updates       : {col: value}
      - branding_updates      : {db_col: value}  (snake_case)
      - settings_updates      : {category: {field: value}}
    Apenas campos conhecidos sao aceitos; resto e ignorado.
    """
    clinics_updates: dict[str, Any] = {}
    branding_updates: dict[str, Any] = {}
    settings_updates: dict[str, dict[str, Any]] = {}

    if "name" in payload:
        clinics_updates["name"] = payload["name"]

    for ui_field, db_field in _BRANDING_FIELDS_UI_TO_DB.items():
        if ui_field in payload:
            branding_updates[db_field] = payload[ui_field]

    for field, category in _FIELD_TO_CATEGORY.items():
        if field in payload:
            settings_updates.setdefault(category, {})[field] = payload[field]

    return clinics_updates, branding_updates, settings_updates


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@clinic_config_bp.get("/config")
@api_role_required("Admin", "AdminClinica", "Medico", "Recepcao", "Financeiro")
def get_clinic_config():
    """Retorna a configuracao do tenant em shape achatado."""
    tenant_id = _resolve_tenant_id()
    clinic_id = getattr(g, "clinic_id", None)
    if tenant_id is None or clinic_id is None:
        return _error(
            "tenant_context_missing",
            "Contexto do tenant nao resolvido para o usuario autenticado.",
            400,
        )

    try:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT id, name, slug FROM clinics WHERE id = %s",
                (clinic_id,),
            )
            clinic = cur.fetchone()
            if not clinic:
                return _error("not_found", "Clinica nao encontrada.", 404)

            cur.execute(
                """
                SELECT brand_name, logo_url, primary_color,
                       secondary_color, subdomain
                FROM tenant_branding
                WHERE tenant_id = %s
                """,
                (tenant_id,),
            )
            branding = cur.fetchone()

            cur.execute(
                "SELECT settings FROM tenant_settings WHERE tenant_id = %s",
                (tenant_id,),
            )
            settings_row = cur.fetchone()
            settings_obj = settings_row["settings"] if settings_row else None

            response = _flatten_payload(clinic, branding, settings_obj)
            response.update(_masked_secret_fields(tenant_id, settings_obj))
            return _success(response)
    except Exception:
        logger.error("Erro ao buscar config do tenant", exc_info=True)
        # Fallback minimo
        return _success({"name": ""})


@clinic_config_bp.patch("/config")
@api_role_required("Admin", "AdminClinica", "Medico", "Recepcao", "Financeiro")
def update_clinic_config():
    """Atualiza a configuracao do tenant. Distribui o payload achatado entre
    clinics, tenant_branding e tenant_settings JSONB."""
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    if not _user_can_edit():
        return _error(
            "forbidden",
            "Apenas administradores da clinica podem alterar configuracoes.",
            403,
        )

    tenant_id = _resolve_tenant_id()
    clinic_id = getattr(g, "clinic_id", None)
    if tenant_id is None or clinic_id is None:
        return _error(
            "tenant_context_missing",
            "Contexto do tenant nao resolvido.",
            400,
        )

    payload = _json_payload()
    clinics_updates, branding_updates, settings_updates = _split_payload(payload)
    secret_updates = _split_secret_payload(payload)
    has_secret_fields = any(field in payload for field in _SECRET_FIELD_TO_INTEGRATION)

    if not (clinics_updates or branding_updates or settings_updates or secret_updates or has_secret_fields):
        return _error("validation_error", "Nenhum campo para atualizar.", 422)

    user_id = int(current_user.id) if current_user.is_authenticated else None

    try:
        with db_cursor(dictionary=True) as (conn, cur):
            # 1. clinics.name
            if clinics_updates:
                cols = ", ".join(f"{k} = %s" for k in clinics_updates)
                cur.execute(
                    f"UPDATE clinics SET {cols}, updated_at = NOW() "
                    f"WHERE id = %s",
                    (*clinics_updates.values(), clinic_id),
                )

            # 2. tenant_branding (UPSERT)
            if branding_updates:
                cur.execute(
                    "SELECT 1 FROM tenant_branding WHERE tenant_id = %s",
                    (tenant_id,),
                )
                exists = cur.fetchone()
                if exists:
                    cols = ", ".join(f"{k} = %s" for k in branding_updates)
                    cur.execute(
                        f"UPDATE tenant_branding SET {cols}, "
                        f"updated_at = CURRENT_TIMESTAMP "
                        f"WHERE tenant_id = %s",
                        (*branding_updates.values(), tenant_id),
                    )
                else:
                    cols = ["tenant_id"] + list(branding_updates.keys())
                    placeholders = ", ".join(["%s"] * len(cols))
                    cur.execute(
                        f"INSERT INTO tenant_branding ({', '.join(cols)}) "
                        f"VALUES ({placeholders})",
                        (tenant_id, *branding_updates.values()),
                    )

            # 3. tenant_settings.settings — UPSERT com merge JSONB
            if settings_updates or secret_updates or has_secret_fields:
                # jsonb_set nao funciona bem para multiplas categorias
                # de uma vez. Estrategia: ler o existente, mesclar em
                # Python, gravar de volta.
                cur.execute(
                    "SELECT settings FROM tenant_settings WHERE tenant_id = %s "
                    "FOR UPDATE",
                    (tenant_id,),
                )
                row = cur.fetchone()
                existing = (row["settings"] if row else None) or {}
                if not isinstance(existing, dict):
                    existing = {}

                for key, value in _legacy_secret_updates(existing).items():
                    secret_updates.setdefault(key, value)

                settings_changed = False
                for category, fields in settings_updates.items():
                    cat = existing.get(category)
                    if not isinstance(cat, dict):
                        cat = {}
                    cat.update(fields)
                    existing[category] = cat
                    settings_changed = True

                settings_changed = _scrub_legacy_secret_settings(existing) or settings_changed

                if row and settings_changed:
                    cur.execute(
                        """
                        UPDATE tenant_settings
                        SET settings = %s::jsonb,
                            updated_at = NOW(),
                            updated_by = %s
                        WHERE tenant_id = %s
                        """,
                        (json.dumps(existing), user_id, tenant_id),
                    )
                elif settings_changed:
                    cur.execute(
                        """
                        INSERT INTO tenant_settings (
                            tenant_id, settings, updated_by
                        )
                        VALUES (%s, %s::jsonb, %s)
                        """,
                        (tenant_id, json.dumps(existing), user_id),
                    )

            conn.commit()

            if secret_updates:
                upsert_integrations(tenant_id, **secret_updates)

            # Retornar o shape achatado atualizado.
            cur.execute(
                "SELECT id, name, slug FROM clinics WHERE id = %s",
                (clinic_id,),
            )
            clinic = cur.fetchone()
            cur.execute(
                "SELECT brand_name, logo_url, primary_color, "
                "secondary_color, subdomain FROM tenant_branding "
                "WHERE tenant_id = %s",
                (tenant_id,),
            )
            branding = cur.fetchone()
            cur.execute(
                "SELECT settings FROM tenant_settings WHERE tenant_id = %s",
                (tenant_id,),
            )
            settings_row = cur.fetchone()
            settings_obj = settings_row["settings"] if settings_row else None

            response = _flatten_payload(clinic, branding, settings_obj)
            response.update(_masked_secret_fields(tenant_id, settings_obj))
            return _success(response)
    except Exception:
        logger.error("Erro ao atualizar config do tenant", exc_info=True)
        return _error("internal_error", "Falha ao salvar configuracao.", 500)
