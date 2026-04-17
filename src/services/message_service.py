# src/services/message_service.py
from __future__ import annotations

import logging

from src.integrations.email import send_email_notification
from src.repositories import message_repository
from src.services.anamnesis_flow import process_message

logger = logging.getLogger("cannabia.message")

CRITICAL_TERMS = ("ajuda", "urgente", "crítico", "critico", "emergência", "emergencia")


def parse_change(data):
    entries = data.get("entry", [])
    if not entries:
        return None, None
    changes = entries[0].get("changes", [])
    if not changes:
        return None, None
    change = changes[0]
    return change.get("field"), change.get("value", {})


def handle_message_event(data: dict, clinic_id: int) -> None:
    """
    Ponto de entrada para eventos de mensagem vindos do webhook Meta.
    1. Salva a mensagem recebida (auditoria)
    2. Verifica termos críticos (alerta imediato ao médico)
    3. Delega ao motor de anamnese (process_message)
    """
    _, value = parse_change(data)
    if not value:
        return

    messages = value.get("messages", [])
    contacts = value.get("contacts", [])

    if not messages:
        return

    msg          = messages[0]
    sender       = msg.get("from", "desconhecido")
    message_text = msg.get("text", {}).get("body", "")
    timestamp    = msg.get("timestamp", "")
    contact_name = (
        contacts[0].get("profile", {}).get("name", "desconhecido")
        if contacts else "desconhecido"
    )

    # Salva mensagem recebida para auditoria (mantido)
    message_repository.save_incoming_message(
        clinic_id, sender, contact_name, message_text, timestamp
    )

    # Registrar na conversa (threading)
    try:
        from src.services.conversation_service import receive_inbound_message

        receive_inbound_message(
            clinic_id,
            sender,
            message_text,
            contact_name=contact_name,
            channel="whatsapp",
            external_id=msg.get("id"),
        )
    except Exception:
        logger.debug("Conversation threading indisponivel (tabela ainda nao aplicada?)")

    text_lower = (message_text or "").lower()

    # Alerta crítico ao médico (mantido, executa antes do fluxo)
    if any(term in text_lower for term in CRITICAL_TERMS):
        subject = "⚠️ [CannabIA] Alerta Crítico — Paciente precisa de atenção"
        body    = (
            f"Uma mensagem crítica foi recebida de {contact_name} ({sender}):\n\n"
            f"{message_text}"
        )
        send_email_notification(subject, body)
        logger.warning("Alerta crítico recebido de %s: %s", sender, message_text[:80])

    # Delega ao motor de anamnese
    try:
        process_message(clinic_id, sender, contact_name, message_text)
    except Exception:
        logger.exception("Erro em process_message para %s", sender)


def handle_status_event(data: dict, clinic_id: int) -> None:
    """Salva atualizações de status de template enviados."""
    field, value = parse_change(data)
    if field != "message_template_status_update":
        return

    message_repository.save_status_update(
        clinic_id,
        value.get("id", ""),
        value.get("status", ""),
        value.get("timestamp", ""),
    )