import hashlib
import hmac
import json
import logging
import os
from typing import Optional

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
    extract_phone_number_id,
    handle_message_event,
    handle_status_event,
    iter_message_changes,
    resolve_tenant_routing,
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


def _verify_hmac_meta(raw_body: bytes, app_secret: Optional[str] = None) -> bool:
    """
    Valida X-Hub-Signature-256 enviada pela Meta no header da request.
    Usa hmac.compare_digest para ser resistente a timing attacks.

    `app_secret` é o segredo do tenant resolvido por phone_number_id (COM-3 /
    29.3 RM5); quando ausente, cai no WHATSAPP_APP_SECRET global. Em produção, ou
    quando WHATSAPP_WEBHOOK_REQUIRE_SIGNATURE=true, a ausência de qualquer segredo
    bloqueia o webhook. Em desenvolvimento, mantém a tolerância legada.
    """
    secret = app_secret or WHATSAPP_APP_SECRET
    if not secret:
        if _strict_meta_webhook_hmac():
            logger.error(
                "Nenhum app_secret (tenant/global) configurado com validação HMAC obrigatória."
            )
            return False
        logger.warning(
            "app_secret não configurado — validação HMAC desativada (dev mode)."
        )
        return True

    header = request.headers.get("X-Hub-Signature-256", "")
    if not header.startswith("sha256="):
        return False

    expected = header[len("sha256="):]
    computed = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, expected)


def _resolve_meta_app_secret(data: dict) -> Optional[str]:
    """
    Resolve o app_secret do tenant pelo 1º phone_number_id do payload (COM-3).
    Extrair o phone_number_id de um payload ainda-não-verificado apenas SELECIONA
    contra qual segredo conferir a assinatura — a verificação HMAC continua
    gateando o processamento. Retorna None para o caller usar o segredo global.
    """
    for _field, value in iter_message_changes(data):
        if not extract_phone_number_id(value):
            continue
        routing = resolve_tenant_routing(value)
        if routing.get("tenant_id") is not None:
            try:
                from src.services.tenant_secrets import get_whatsapp_config

                return get_whatsapp_config(routing["tenant_id"]).get("app_secret")
            except Exception:
                logger.exception(
                    "Falha ao resolver app_secret do tenant %s", routing["tenant_id"]
                )
        return None
    return None


def _strict_meta_webhook_hmac() -> bool:
    explicit = os.getenv("WHATSAPP_WEBHOOK_REQUIRE_SIGNATURE", "").strip().lower()
    if explicit in {"1", "true", "yes", "on"}:
        return True
    return os.getenv("FLASK_ENV", "").strip().lower() == "production"


def _process_meta_payload(data: dict, clinic_id: int) -> None:
    """
    Despacha eventos Meta para os handlers de negócio, varrendo TODOS os
    entry[].changes[] do payload (COM-2). `clinic_id` é o fallback padrão da
    request; a resolução de tenant por `phone_number_id` é feita por mensagem
    no handler quando aplicável (COM-3).
    """
    for field, value in iter_message_changes(data):
        if field == "messages":
            routing = resolve_tenant_routing(value, default_clinic_id=clinic_id)
            handle_message_event(
                value, routing["clinic_id"], tenant_id=routing["tenant_id"]
            )
            socketio.emit("new_message", redact_dict(value))

        elif field == "message_template_status_update":
            routing = resolve_tenant_routing(value, default_clinic_id=clinic_id)
            handle_status_event(value, routing["clinic_id"])
            socketio.emit("status_update", redact_dict(value))


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

    # Parse leniente para rotear o segredo de verificação pelo phone_number_id
    # (COM-3). A assinatura ainda gateia o processamento abaixo.
    try:
        routing_data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except (ValueError, UnicodeDecodeError):
        routing_data = {}
    if not isinstance(routing_data, dict):
        routing_data = {}

    app_secret = _resolve_meta_app_secret(routing_data)
    if not _verify_hmac_meta(raw_body, app_secret):
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
    # Skeleton reservado para integração Twilio futura. Até existir parser +
    # validação X-Twilio-Signature, retornar 501 evita aceitar payloads
    # arbitrários e sinaliza claramente que o endpoint não está implementado.
    # Quando a integração for priorizada, substituir por handler real.
    logger.info("Webhook Twilio recebido — endpoint nao implementado (501).")
    abort(501, "Webhook Twilio not yet implemented")


# ──────────────────────────────────────────────
# ROTA: Z-API (skeleton)
# ──────────────────────────────────────────────

@realtime_bp.route("/webhook/zapi", methods=["POST"])
def webhook_zapi():
    # Skeleton reservado para integração Z-API futura. Até existir parser +
    # validação de token Bearer, retornar 501 evita aceitar payloads
    # arbitrários e sinaliza claramente que o endpoint não está implementado.
    # Quando a integração for priorizada, substituir por handler real.
    logger.info("Webhook Z-API recebido — endpoint nao implementado (501).")
    abort(501, "Webhook Z-API not yet implemented")


# ──────────────────────────────────────────────
# SOCKET & DASHBOARD
# ──────────────────────────────────────────────

@socketio.on("connect")
def socket_connect():
    if not current_user.is_authenticated:
        return False


@realtime_bp.route("/")
@role_required("Admin", "AdminClinica", "Medico", "Recepcao")
def realtime_dashboard():
    return render_template("realtime_dashboard.html")
