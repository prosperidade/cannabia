"""Service para gerenciamento de conversas clinicas."""

from __future__ import annotations

from typing import Optional

from src.repositories.conversation_repository import (
    add_message,
    assign_conversation,
    close_conversation,
    get_or_create_conversation,
    list_conversations,
    get_conversation,
    list_messages,
    mark_conversation_read,
    update_conversation_on_message,
)


def receive_inbound_message(
    clinic_id: int,
    contact_phone: str,
    message_text: str,
    *,
    contact_name: Optional[str] = None,
    patient_id: Optional[int] = None,
    channel: str = "whatsapp",
    external_id: Optional[str] = None,
    message_type: str = "text",
) -> dict:
    """Registra uma mensagem recebida e atualiza/cria a conversa."""
    conv = get_or_create_conversation(
        clinic_id,
        contact_phone,
        contact_name=contact_name,
        patient_id=patient_id,
        channel=channel,
    )

    msg = add_message(
        conv["id"],
        clinic_id,
        direction="inbound",
        sender_type="patient",
        sender_name=contact_name,
        message_text=message_text,
        message_type=message_type,
        external_id=external_id,
    )

    update_conversation_on_message(
        conv["id"],
        last_message_preview=message_text or "",
        increment_unread=True,
    )

    return {"conversation_id": conv["id"], "message_id": msg["id"]}


def send_outbound_message(
    clinic_id: int,
    conversation_id: int,
    message_text: str,
    *,
    sender_name: Optional[str] = None,
    sender_user_id: Optional[int] = None,
) -> dict:
    """Registra uma mensagem enviada pela clinica e tenta enviar via WhatsApp."""
    conv = get_conversation(conversation_id, clinic_id)
    if not conv:
        raise ValueError("Conversa nao encontrada.")

    msg = add_message(
        conversation_id,
        clinic_id,
        direction="outbound",
        sender_type="clinic",
        sender_name=sender_name,
        message_text=message_text,
    )

    update_conversation_on_message(
        conversation_id,
        last_message_preview=message_text or "",
        increment_unread=False,
    )

    # Tentar enviar via WhatsApp (best-effort)
    sent = False
    try:
        from src.integrations.whatsapp import send_whatsapp_text

        send_whatsapp_text(conv["contact_phone"], message_text)
        sent = True
    except Exception:
        pass

    return {"message_id": msg["id"], "sent_via_whatsapp": sent}
