# src/services/tenant_secrets.py
"""
Resolve credenciais e configuracoes por tenant com fallback para variaveis de ambiente.

Uso:
    from src.services.tenant_secrets import get_whatsapp_config

    cfg = get_whatsapp_config(tenant_id=tenant_id)
    # {"phone_number_id": "...", "access_token": "...", "app_secret": "..."}

Se o tenant nao tiver valores configurados, cai no src.config (variaveis de ambiente).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Optional

from src.repositories.tenant_settings_repository import get_integrations

logger = logging.getLogger("cannabia.tenant_secrets")


def _load_env_fallback() -> dict[str, Any]:
    """Carrega valores globais do src.config. Cacheado por processo."""
    from src import config as _cfg
    return {
        "whatsapp_phone_number_id": _cfg.WHATSAPP_PHONE_NUMBER_ID,
        "meta_whatsapp_key": _cfg.META_WHATSAPP_KEY,
        "whatsapp_app_secret": _cfg.WHATSAPP_APP_SECRET,
        "verify_token": _cfg.VERIFY_TOKEN,
        "email_from": _cfg.EMAIL_FROM,
        "smtp_server": _cfg.SMTP_SERVER,
        "smtp_port": _cfg.SMTP_PORT,
        "email_password": _cfg.EMAIL_PASSWORD,
        "doctor_email": _cfg.DOCTOR_EMAIL,
        "google_api_key": _cfg.GOOGLE_API_KEY,
    }


def _tenant_integrations(tenant_id: Optional[int]) -> Optional[dict[str, Any]]:
    if tenant_id is None:
        return None
    try:
        return get_integrations(int(tenant_id), decrypted=True)
    except Exception as exc:
        logger.warning("Falha ao carregar integrations do tenant %s: %s", tenant_id, exc)
        return None


def _resolve(tenant_value: Optional[Any], env_value: Optional[Any]) -> Optional[Any]:
    if tenant_value not in (None, ""):
        return tenant_value
    return env_value


def get_whatsapp_config(tenant_id: Optional[int] = None) -> dict[str, Any]:
    env = _load_env_fallback()
    integ = _tenant_integrations(tenant_id) or {}

    return {
        "phone_number_id": _resolve(
            integ.get("whatsapp_phone_number_id"), env["whatsapp_phone_number_id"]
        ),
        "access_token": _resolve(
            integ.get("meta_whatsapp_key"), env["meta_whatsapp_key"]
        ),
        "app_secret": _resolve(
            integ.get("whatsapp_app_secret"), env["whatsapp_app_secret"]
        ),
        "verify_token": _resolve(
            integ.get("verify_token"), env["verify_token"]
        ),
        "business_account_id": integ.get("whatsapp_business_account_id"),
    }


def get_email_config(tenant_id: Optional[int] = None) -> dict[str, Any]:
    env = _load_env_fallback()
    integ = _tenant_integrations(tenant_id) or {}

    return {
        "email_from": _resolve(integ.get("email_from"), env["email_from"]),
        "smtp_server": _resolve(integ.get("smtp_server"), env["smtp_server"]),
        "smtp_port": _resolve(integ.get("smtp_port"), env["smtp_port"]),
        "email_password": _resolve(integ.get("email_password"), env["email_password"]),
        "doctor_email": _resolve(integ.get("doctor_email"), env["doctor_email"]),
    }


def get_ai_config(tenant_id: Optional[int] = None) -> dict[str, Any]:
    env = _load_env_fallback()
    integ = _tenant_integrations(tenant_id) or {}

    return {
        "provider": integ.get("ai_provider") or "gemini",
        "google_api_key": _resolve(integ.get("ai_api_key"), env["google_api_key"]),
        "openai_api_key": integ.get("openai_api_key"),
    }


def invalidate_cache(tenant_id: Optional[int] = None) -> None:
    """
    Placeholder para invalidacao de cache por tenant.
    Atualmente a leitura e direta ao banco; mantido para extensibilidade.
    """
    return None
