# src/services/message_service.py
from __future__ import annotations

import logging
from typing import Optional

from src.config import DEFAULT_CLINIC_ID
from src.integrations.email import send_email_notification
from src.repositories import message_repository
from src.services.anamnesis_flow import process_message

logger = logging.getLogger("cannabia.message")

CRITICAL_TERMS = ("ajuda", "urgente", "crítico", "critico", "emergência", "emergencia")


def extract_phone_number_id(value: dict) -> Optional[str]:
    """Lê value.metadata.phone_number_id (presente em todo payload Meta)."""
    return ((value or {}).get("metadata") or {}).get("phone_number_id")


def resolve_tenant_routing(value: dict, default_clinic_id: int = DEFAULT_CLINIC_ID) -> dict:
    """
    Resolve {clinic_id, tenant_id} por value.metadata.phone_number_id (COM-3 /
    29.3 RM5), encerrando o vazamento cross-tenant em que toda mensagem caía na
    clínica default. Sem match (ou sem phone_number_id): fallback ao
    `default_clinic_id` com WARNING.
    """
    phone_number_id = extract_phone_number_id(value)
    if phone_number_id:
        try:
            from src.repositories.tenant_settings_repository import (
                resolve_tenant_by_phone_number_id,
            )
            match = resolve_tenant_by_phone_number_id(phone_number_id)
        except Exception:
            logger.exception(
                "Falha ao resolver tenant por phone_number_id=%s", phone_number_id
            )
            match = None
        if match:
            return {
                "clinic_id": match.get("clinic_id") or default_clinic_id,
                "tenant_id": match.get("tenant_id"),
            }
        logger.warning(
            "Nenhum tenant ativo para phone_number_id=%s — fallback clinic_id=%s",
            phone_number_id,
            default_clinic_id,
        )
    return {"clinic_id": default_clinic_id, "tenant_id": None}


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


def handle_message_event(value: dict, clinic_id: int, tenant_id: Optional[int] = None) -> None:
    """
    Processa um `value` Meta de field="messages", iterando TODAS as mensagens
    do batch (COM-2). Cada mensagem é processada de forma isolada: uma falha
    individual não interrompe as demais. `tenant_id` (COM-3) é propagado ao
    outbound para usar a credencial WhatsApp do tenant resolvido.
    """
    messages = value.get("messages", []) or []
    contacts = value.get("contacts", []) or []

    for msg in messages:
        try:
            _process_single_message(msg, contacts, clinic_id, tenant_id)
        except Exception:
            logger.exception(
                "Falha ao processar mensagem inbound (wamid=%s)", msg.get("id")
            )


def _process_single_message(
    msg: dict, contacts: list, clinic_id: int, tenant_id: Optional[int] = None
) -> None:
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
    wamid        = msg.get("id")
    contact_name = _resolve_contact_name(msg, contacts)

    # Salva mensagem recebida para auditoria; idempotente por (clinic_id, wamid).
    inserted_id = message_repository.save_incoming_message(
        clinic_id, sender, contact_name, message_text, timestamp, wamid=wamid
    )

    # Curto-circuito de idempotencia (COM-1 / 29.3 RM1): wamid ja visto -> a
    # reentrega da Meta nao reprocessa (sem duplicar conversa nem avancar 2x a
    # maquina de estados da anamnese).
    if wamid and inserted_id is None:
        logger.info("Mensagem Meta duplicada ignorada (wamid=%s)", wamid)
        return

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

    # Delega ao motor de anamnese (tenant_id propagado ao outbound — COM-3)
    try:
        process_message(clinic_id, sender, contact_name, message_text, tenant_id=tenant_id)
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
