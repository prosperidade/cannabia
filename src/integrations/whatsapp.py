"""
Integracao Meta WhatsApp Business API.

Quando `tenant_id` e fornecido, as credenciais sao resolvidas por tenant com
fallback para variaveis de ambiente globais. Isso viabiliza multi-tenancy com
credenciais isoladas por organizacao.
"""

from __future__ import annotations

from typing import Optional

import requests

from src.services.tenant_secrets import get_whatsapp_config


def _resolve_config(tenant_id: Optional[int] = None) -> dict:
    cfg = get_whatsapp_config(tenant_id)
    if not cfg.get("access_token"):
        raise ValueError(
            "Token WhatsApp nao configurado. Verifique tenant_integrations ou META_WHATSAPP_KEY."
        )
    if not cfg.get("phone_number_id"):
        raise ValueError(
            "phone_number_id nao configurado. Verifique tenant_integrations ou WHATSAPP_PHONE_NUMBER_ID."
        )
    return cfg


def send_whatsapp_template(
    recipient_phone: Optional[str] = None,
    template_name: str = "hello_world",
    language_code: str = "en_US",
    *,
    tenant_id: Optional[int] = None,
):
    cfg = _resolve_config(tenant_id)

    # Fallback para RECIPIENT_PHONE quando nao passado
    if recipient_phone is None:
        from src.config import RECIPIENT_PHONE
        recipient_phone = RECIPIENT_PHONE

    if not recipient_phone:
        raise ValueError("recipient_phone nao informado e RECIPIENT_PHONE ausente no .env")

    url = f"https://graph.facebook.com/v22.0/{cfg['phone_number_id']}/messages"
    headers = {
        "Authorization": f"Bearer {cfg['access_token']}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        },
    }
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    return response.json()


def send_whatsapp_text(
    recipient_phone: str,
    text: str,
    *,
    tenant_id: Optional[int] = None,
) -> dict:
    """
    Envia mensagem de texto livre (nao-template). Funciona dentro da janela
    de 24h apos o paciente iniciar a conversa.
    """
    cfg = _resolve_config(tenant_id)

    url = f"https://graph.facebook.com/v22.0/{cfg['phone_number_id']}/messages"
    headers = {
        "Authorization": f"Bearer {cfg['access_token']}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "text",
        "text": {"body": text},
    }
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    return response.json()
