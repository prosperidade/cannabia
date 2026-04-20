# src/repositories/tenant_settings_repository.py
"""
Repositorio de configuracoes por tenant: branding e integrations.

Segredos (API keys, senhas) sao persistidos criptografados via Fernet.
O acesso de leitura retorna valores descriptografados (ou None quando ausentes).
"""

from __future__ import annotations

from typing import Any, Optional

from src.infra.crypto import decrypt_value, encrypt_value
from src.infra.database import db_cursor


# ═══════════════════════════════════════════════════════════════════════════
# Branding
# ═══════════════════════════════════════════════════════════════════════════

def get_branding(tenant_id: int) -> Optional[dict[str, Any]]:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT tenant_id, brand_name, logo_url, primary_color,
                   secondary_color, subdomain, created_at, updated_at
            FROM tenant_branding
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        )
        return cursor.fetchone()


def upsert_branding(
    tenant_id: int,
    *,
    brand_name: Optional[str] = None,
    logo_url: Optional[str] = None,
    primary_color: Optional[str] = None,
    secondary_color: Optional[str] = None,
    subdomain: Optional[str] = None,
) -> dict[str, Any]:
    normalized_subdomain = (subdomain or "").strip().lower() or None

    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO tenant_branding (
                tenant_id, brand_name, logo_url, primary_color, secondary_color, subdomain
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id) DO UPDATE SET
                brand_name      = COALESCE(EXCLUDED.brand_name, tenant_branding.brand_name),
                logo_url        = COALESCE(EXCLUDED.logo_url, tenant_branding.logo_url),
                primary_color   = COALESCE(EXCLUDED.primary_color, tenant_branding.primary_color),
                secondary_color = COALESCE(EXCLUDED.secondary_color, tenant_branding.secondary_color),
                subdomain       = COALESCE(EXCLUDED.subdomain, tenant_branding.subdomain),
                updated_at      = CURRENT_TIMESTAMP
            RETURNING tenant_id, brand_name, logo_url, primary_color,
                      secondary_color, subdomain, updated_at
            """,
            (
                tenant_id,
                brand_name,
                logo_url,
                primary_color,
                secondary_color,
                normalized_subdomain,
            ),
        )
        row = cursor.fetchone()
        conn.commit()
        return row


def resolve_tenant_by_subdomain(subdomain: str) -> Optional[dict[str, Any]]:
    """Resolve tenant a partir do subdominio (case-insensitive)."""
    normalized = (subdomain or "").strip().lower()
    if not normalized:
        return None

    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT t.id AS tenant_id, t.slug, t.display_name, t.status,
                   t.legacy_clinic_id AS clinic_id, tb.brand_name
            FROM tenant_branding tb
            JOIN tenants t ON t.id = tb.tenant_id
            WHERE LOWER(tb.subdomain) = %s
              AND t.status = 'active'
            LIMIT 1
            """,
            (normalized,),
        )
        return cursor.fetchone()


# ═══════════════════════════════════════════════════════════════════════════
# Integrations (secrets criptografados)
# ═══════════════════════════════════════════════════════════════════════════

_ENCRYPTED_FIELDS = {
    "meta_whatsapp_key",
    "email_password",
    "ai_api_key",
    "whatsapp_app_secret",
    "verify_token",
    "openai_api_key",
}


def _decrypt_safe(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return decrypt_value(value)
    except ValueError:
        return None


def get_integrations(tenant_id: int, *, decrypted: bool = True) -> Optional[dict[str, Any]]:
    """
    Retorna integrations do tenant. Quando `decrypted=True`, devolve os segredos
    em claro (para uso interno). Quando `decrypted=False`, mascarar valores.
    """
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT tenant_id,
                   whatsapp_phone_number_id,
                   whatsapp_business_account_id,
                   meta_whatsapp_key_encrypted,
                   email_from,
                   smtp_server,
                   smtp_port,
                   email_password_encrypted,
                   ai_provider,
                   ai_api_key_encrypted,
                   whatsapp_app_secret_encrypted,
                   verify_token_encrypted,
                   openai_api_key_encrypted,
                   doctor_email,
                   created_at,
                   updated_at
            FROM tenant_integrations
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        )
        row = cursor.fetchone()

    if not row:
        return None

    if decrypted:
        row["meta_whatsapp_key"] = _decrypt_safe(row.pop("meta_whatsapp_key_encrypted"))
        row["email_password"] = _decrypt_safe(row.pop("email_password_encrypted"))
        row["ai_api_key"] = _decrypt_safe(row.pop("ai_api_key_encrypted"))
        row["whatsapp_app_secret"] = _decrypt_safe(row.pop("whatsapp_app_secret_encrypted"))
        row["verify_token"] = _decrypt_safe(row.pop("verify_token_encrypted"))
        row["openai_api_key"] = _decrypt_safe(row.pop("openai_api_key_encrypted"))
    else:
        for key in list(row.keys()):
            if key.endswith("_encrypted"):
                base = key.replace("_encrypted", "")
                row[base] = "***" if row.pop(key) else None

    return row


def upsert_integrations(
    tenant_id: int,
    *,
    whatsapp_phone_number_id: Optional[str] = None,
    whatsapp_business_account_id: Optional[str] = None,
    meta_whatsapp_key: Optional[str] = None,
    whatsapp_app_secret: Optional[str] = None,
    verify_token: Optional[str] = None,
    email_from: Optional[str] = None,
    smtp_server: Optional[str] = None,
    smtp_port: Optional[int] = None,
    email_password: Optional[str] = None,
    doctor_email: Optional[str] = None,
    ai_provider: Optional[str] = None,
    ai_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
) -> dict[str, Any]:
    def _enc(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if value == "":
            # Limpar segredo explicitamente
            return ""
        return encrypt_value(value)

    encrypted_values = {
        "meta_whatsapp_key_encrypted": _enc(meta_whatsapp_key),
        "email_password_encrypted": _enc(email_password),
        "ai_api_key_encrypted": _enc(ai_api_key),
        "whatsapp_app_secret_encrypted": _enc(whatsapp_app_secret),
        "verify_token_encrypted": _enc(verify_token),
        "openai_api_key_encrypted": _enc(openai_api_key),
    }

    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO tenant_integrations (
                tenant_id,
                whatsapp_phone_number_id,
                whatsapp_business_account_id,
                meta_whatsapp_key_encrypted,
                whatsapp_app_secret_encrypted,
                verify_token_encrypted,
                email_from,
                smtp_server,
                smtp_port,
                email_password_encrypted,
                doctor_email,
                ai_provider,
                ai_api_key_encrypted,
                openai_api_key_encrypted
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id) DO UPDATE SET
                whatsapp_phone_number_id       = COALESCE(EXCLUDED.whatsapp_phone_number_id, tenant_integrations.whatsapp_phone_number_id),
                whatsapp_business_account_id   = COALESCE(EXCLUDED.whatsapp_business_account_id, tenant_integrations.whatsapp_business_account_id),
                meta_whatsapp_key_encrypted    = COALESCE(EXCLUDED.meta_whatsapp_key_encrypted, tenant_integrations.meta_whatsapp_key_encrypted),
                whatsapp_app_secret_encrypted  = COALESCE(EXCLUDED.whatsapp_app_secret_encrypted, tenant_integrations.whatsapp_app_secret_encrypted),
                verify_token_encrypted         = COALESCE(EXCLUDED.verify_token_encrypted, tenant_integrations.verify_token_encrypted),
                email_from                     = COALESCE(EXCLUDED.email_from, tenant_integrations.email_from),
                smtp_server                    = COALESCE(EXCLUDED.smtp_server, tenant_integrations.smtp_server),
                smtp_port                      = COALESCE(EXCLUDED.smtp_port, tenant_integrations.smtp_port),
                email_password_encrypted       = COALESCE(EXCLUDED.email_password_encrypted, tenant_integrations.email_password_encrypted),
                doctor_email                   = COALESCE(EXCLUDED.doctor_email, tenant_integrations.doctor_email),
                ai_provider                    = COALESCE(EXCLUDED.ai_provider, tenant_integrations.ai_provider),
                ai_api_key_encrypted           = COALESCE(EXCLUDED.ai_api_key_encrypted, tenant_integrations.ai_api_key_encrypted),
                openai_api_key_encrypted       = COALESCE(EXCLUDED.openai_api_key_encrypted, tenant_integrations.openai_api_key_encrypted),
                updated_at                     = CURRENT_TIMESTAMP
            RETURNING tenant_id
            """,
            (
                tenant_id,
                whatsapp_phone_number_id,
                whatsapp_business_account_id,
                encrypted_values["meta_whatsapp_key_encrypted"],
                encrypted_values["whatsapp_app_secret_encrypted"],
                encrypted_values["verify_token_encrypted"],
                email_from,
                smtp_server,
                smtp_port,
                encrypted_values["email_password_encrypted"],
                doctor_email,
                ai_provider,
                encrypted_values["ai_api_key_encrypted"],
                encrypted_values["openai_api_key_encrypted"],
            ),
        )
        conn.commit()

    return get_integrations(tenant_id, decrypted=False)


# ═══════════════════════════════════════════════════════════════════════════
# Plano e quotas
# ═══════════════════════════════════════════════════════════════════════════

def get_tenant_quota(tenant_id: int) -> Optional[dict[str, Any]]:
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT id AS tenant_id,
                   billing_plan,
                   ai_executions_month,
                   ai_limit_month,
                   user_limit,
                   quota_reset_at
            FROM tenants
            WHERE id = %s
            """,
            (tenant_id,),
        )
        return cursor.fetchone()


def update_tenant_plan(
    tenant_id: int,
    *,
    billing_plan: Optional[str] = None,
    ai_limit_month: Optional[int] = None,
    user_limit: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    sets = []
    params: list[Any] = []

    if billing_plan is not None:
        sets.append("billing_plan = %s")
        params.append(billing_plan)
    if ai_limit_month is not None:
        sets.append("ai_limit_month = %s")
        params.append(int(ai_limit_month))
    if user_limit is not None:
        sets.append("user_limit = %s")
        params.append(int(user_limit))

    if not sets:
        return get_tenant_quota(tenant_id)

    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.append(tenant_id)

    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            f"""
            UPDATE tenants SET {', '.join(sets)}
            WHERE id = %s
            RETURNING id AS tenant_id, billing_plan, ai_executions_month,
                      ai_limit_month, user_limit
            """,
            params,
        )
        row = cursor.fetchone()
        conn.commit()
        return row


def increment_ai_usage(tenant_id: int, amount: int = 1) -> None:
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            UPDATE tenants
            SET ai_executions_month = ai_executions_month + %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (int(amount), tenant_id),
        )
        conn.commit()
