from src.integrations.email import send_email_notification
from src.integrations.whatsapp import send_whatsapp_template
from src.repositories import message_repository


CRITICAL_TERMS = ("ajuda", "urgente", "crítico")
AUTO_REPLY_TERMS = ("oi", "olá", "td bem", "tudo bem")


def parse_change(data):
    entries = data.get("entry", [])
    if not entries:
        return None, None

    changes = entries[0].get("changes", [])
    if not changes:
        return None, None

    change = changes[0]
    return change.get("field"), change.get("value", {})


def handle_message_event(data):
    _, value = parse_change(data)
    if value is None:
        return

    messages = value.get("messages", [])
    contacts = value.get("contacts", [])
    if not messages:
        return

    msg = messages[0]
    sender = msg.get("from", "desconhecido")
    message_text = msg.get("text", {}).get("body", "")
    timestamp = msg.get("timestamp", "")

    if contacts:
        contact_name = contacts[0].get("profile", {}).get("name", "desconhecido")
    else:
        contact_name = "desconhecido"

    message_repository.ensure_message_tables()
    message_repository.save_incoming_message(sender, contact_name, message_text, timestamp)

    text = (message_text or "").lower()

    if any(term in text for term in AUTO_REPLY_TERMS):
        send_whatsapp_template(
            recipient_phone=sender,
            template_name="hello_world",
            language_code="en_US",
        )

    if any(term in text for term in CRITICAL_TERMS):
        subject = "Alerta Crítico no Sistema Cannab'IA"
        email_message = f"Uma mensagem crítica foi recebida:\n\n{message_text}"
        send_email_notification(subject, email_message)


def handle_status_event(data):
    field, value = parse_change(data)
    if field != "message_template_status_update":
        return

    message_repository.ensure_message_tables()
    message_repository.save_status_update(
        value.get("id", ""),
        value.get("status", ""),
        value.get("timestamp", ""),
    )
