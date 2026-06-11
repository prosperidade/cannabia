# src/services/message_service.py
from __future__ import annotations

import logging

from src.integrations.email import send_email_notification
from src.repositories import message_repository
from src.services.anamnesis_flow import process_message

logger = logging.getLogger("cannabia.message")

CRITICAL_TERMS = ("ajuda", "urgente", "crítico", "critico", "emergência", "emergencia")


def parse_change(data):
    """
    Retorna (field, value) do PRIMEIRO entry/change do payload.
    Mantido por compatibilidade; o caminho de processamento usa
    `iter_message_changes` para varrer o payload inteiro (COM-2).
    """
    entries = data.get("entry", [])
    if not entries:
        return None, None
    changes = entries[0].get("changes", [])
    if not changes:
        return None, None
    change = changes[0]
    return change.get("field"), change.get("value", {})


def iter_message_changes(data: dict):
    """
    Itera (field, value) de TODOS os entry[].changes[] do payload Meta.

    A Meta agrega múltiplas mensagens/entries num único POST em pico de volume;
    ler apenas entry[0].changes[0] (comportamento legado) descartava silenciosamente
    as mensagens 2..N (29.3 P3/RM2). Este gerador preserva a ordem do payload.
    """
    for entry in data.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            yield change.get("field"), (change.get("value") or {})


def _resolve_contact_name(msg: dict, contacts: list) -> str:
    """Casa o remetente da mensagem com seu contato pelo wa_id; fallback ao 1º."""
    sender = msg.get("from")
    for contact in contacts or []:
        if contact.get("wa_id") == sender:
            return contact.get("profile", {}).get("name") or "desconhecido"
    if contacts:
        return contacts[0].get("profile", {}).get("name") or "desconhecido"
    return "desconhecido"


def handle_message_event(value: dict, clinic_id: int) -> None:
    """
    Processa um `value` Meta de field="messages", iterando TODAS as mensagens
    do batch (COM-2). Cada mensagem é processada de forma isolada: uma falha
    individual não interrompe as demais.
    """
    messages = value.get("messages", []) or []
    contacts = value.get("contacts", []) or []

    for msg in messages:
        try:
            _process_single_message(msg, contacts, clinic_id)
        except Exception:
            logger.exception(
                "Falha ao processar mensagem inbound (wamid=%s)", msg.get("id")
            )


def _process_single_message(msg: dict, contacts: list, clinic_id: int) -> None:
    """
    Trata uma única mensagem inbound:
    1. Salva a mensagem recebida (auditoria)
    2. Registra na conversa (threading)
    3. Verifica termos críticos (alerta imediato ao médico)
    4. Delega ao motor de anamnese (process_message)
    """
    sender       = msg.get("from", "desconhecido")
    message_text = msg.get("text", {}).get("body", "")
    timestamp    = msg.get("timestamp", "")
    contact_name = _resolve_contact_name(msg, contacts)

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


def handle_status_event(value: dict, clinic_id: int) -> None:
    """Salva atualizações de status de template enviados (field já filtrado)."""
    message_repository.save_status_update(
        clinic_id,
        value.get("id", ""),
        value.get("status", ""),
        value.get("timestamp", ""),
    )
