import hashlib
import hmac
import logging
import os

from flask import Blueprint, abort, render_template, request, g
from flask_socketio import SocketIO
from flask_login import current_user

from src.web.routes.auth import limit_or_429
from src.infra.security import role_required, redact_dict
from src.config import (
    DEFAULT_CLINIC_ID,
    MAX_CONTENT_LENGTH,
    VERIFY_TOKEN,
    WEBHOOK_RATE_LIMIT,
    WEBHOOK_RATE_WINDOW_S,
    WHATSAPP_APP_SECRET,
)
from src.services.message_service import (
    handle_message_event,
    handle_status_event,
    parse_change,
)

logger = logging.getLogger("cannabia.webhook")
socketio = SocketIO()
realtime_bp = Blueprint("realtime", __name__, template_folder="templates")


# ──────────────────────────────────────────────
# HELPERS COMPARTILHADOS
# ──────────────────────────────────────────────

def _validate_webhook_payload(data) -> bool:
    """Valida estrutura mínima do payload WhatsApp."""
    if not isinstance(data, dict):
        return False
    entries = data.get("entry")
    if not isinstance(entries, list) or not entries:
        return False
    changes = entries[0].get("changes", [])
    return isinstance(changes, list) and bool(changes)


def _verify_hmac_meta(raw_body: bytes) -> bool:
    """
    Valida X-Hub-Signature-256 enviada pela Meta no header da request.
    Usa hmac.compare_digest para ser resistente a timing attacks.
    Em produção, ou quando WHATSAPP_WEBHOOK_REQUIRE_SIGNATURE=true, a ausência
    de WHATSAPP_APP_SECRET bloqueia o webhook. Em desenvolvimento, mantém a
    tolerância legada para facilitar testes locais.
    """
    if not WHATSAPP_APP_SECRET:
        if _strict_meta_webhook_hmac():
            logger.error(
                "WHATSAPP_APP_SECRET não configurado com validação HMAC obrigatória."
            )
            return False
        logger.warning(
            "WHATSAPP_APP_SECRET não configurado — validação HMAC desativada (dev mode)."
        )
        return True

    header = request.headers.get("X-Hub-Signature-256", "")
    if not header.startswith("sha256="):
        return False

    expected = header[len("sha256="):]
    computed = hmac.new(
        WHATSAPP_APP_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, expected)


def _strict_meta_webhook_hmac() -> bool:
    explicit = os.getenv("WHATSAPP_WEBHOOK_REQUIRE_SIGNATURE", "").strip().lower()
    if explicit in {"1", "true", "yes", "on"}:
        return True
    return os.getenv("FLASK_ENV", "").strip().lower() == "production"


def _process_meta_payload(data: dict, clinic_id: int) -> None:
    """Despacha eventos Meta para os handlers de negócio."""
    field, _ = parse_change(data)

    if field == "messages":
        handle_message_event(data, clinic_id)
        socketio.emit("new_message", redact_dict(data))

    elif field == "message_template_status_update":
        handle_status_event(data, clinic_id)
        socketio.emit("status_update", redact_dict(data))


# ──────────────────────────────────────────────
# ROTA: META (WhatsApp Business API)
# ──────────────────────────────────────────────

@realtime_bp.route("/webhook/meta", methods=["GET", "POST"])
def webhook_meta():
    # GET — Verificação de registro do webhook pela Meta
    if request.method == "GET":
        mode      = request.args.get("hub.mode")
        token     = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode and token:
            if mode == "subscribe" and token == VERIFY_TOKEN:
                return challenge, 200
            return "Falha na verificação", 403
        return "Parâmetros ausentes", 400

    # POST — Recebimento de eventos
    limit_or_429("webhook_meta", WEBHOOK_RATE_LIMIT, WEBHOOK_RATE_WINDOW_S)

    if request.content_length and request.content_length > MAX_CONTENT_LENGTH:
        abort(413, description="Payload muito grande.")

    # 🔐 Validação HMAC — body deve ser lido como raw ANTES do parse JSON
    raw_body = request.get_data()
    if not _verify_hmac_meta(raw_body):
        logger.warning("Webhook Meta rejeitado: assinatura HMAC inválida.")
        abort(403, description="Assinatura HMAC inválida.")

    data = request.json or {}
    if not _validate_webhook_payload(data):
        return "Payload inválido", 400

    clinic_id = getattr(g, "clinic_id", None) or DEFAULT_CLINIC_ID

    try:
        _process_meta_payload(data, clinic_id)
    except Exception:
        logger.exception("Erro ao processar webhook Meta")
        return "Erro ao processar webhook", 500

    return "Evento recebido", 200


# ──────────────────────────────────────────────
# ROTA: TWILIO (skeleton)
# ──────────────────────────────────────────────

@realtime_bp.route("/webhook/twilio", methods=["POST"])
def webhook_twilio():
    # TODO: Implementar validação X-Twilio-Signature
    # TODO: Implementar parser de mensagens Twilio
    # TODO: Normalizar para o formato interno e chamar handle_message_event
    logger.info("Webhook Twilio recebido — implementação pendente.")
    return "OK", 200


# ──────────────────────────────────────────────
# ROTA: Z-API (skeleton)
# ──────────────────────────────────────────────

@realtime_bp.route("/webhook/zapi", methods=["POST"])
def webhook_zapi():
    # TODO: Implementar validação de token Bearer Z-API
    # TODO: Implementar parser de mensagens Z-API
    # TODO: Normalizar para o formato interno e chamar handle_message_event
    logger.info("Webhook Z-API recebido — implementação pendente.")
    return "OK", 200


# ──────────────────────────────────────────────
# SOCKET & DASHBOARD
# ──────────────────────────────────────────────

@socketio.on("connect")
def socket_connect():
    if not current_user.is_authenticated:
        return False


@realtime_bp.route("/")
@role_required("Admin", "Medico", "Atendente")
def realtime_dashboard():
    return render_template("realtime_dashboard.html")
