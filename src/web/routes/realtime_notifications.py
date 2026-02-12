from flask import Blueprint, abort, render_template, request
from flask_socketio import SocketIO
from flask_login import current_user

from src.web.routes.auth import limit_or_429, role_required
from src.config import (
    MAX_CONTENT_LENGTH,
    VERIFY_TOKEN,
    WEBHOOK_RATE_LIMIT,
    WEBHOOK_RATE_WINDOW_S,
)
from src.infra.security import redact_dict
from src.services.message_service import (
    handle_message_event,
    handle_status_event,
    parse_change,
)

socketio = SocketIO()
realtime_bp = Blueprint("realtime", __name__, template_folder="templates")


def _validate_webhook_payload(data):
    if not isinstance(data, dict):
        return False
    entries = data.get("entry")
    if not isinstance(entries, list) or not entries:
        return False
    changes = entries[0].get("changes", [])
    if not isinstance(changes, list) or not changes:
        return False
    return True


@socketio.on("connect")
def socket_connect():
    # Flask-Login é o seu mecanismo real de auth
    if not current_user.is_authenticated:
        return False


@realtime_bp.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode and token:
            if mode == "subscribe" and token == VERIFY_TOKEN:
                return challenge, 200
            return "Falha na verificação", 403
        return "Parâmetros ausentes", 400

    # POST
    limit_or_429("webhook", WEBHOOK_RATE_LIMIT, WEBHOOK_RATE_WINDOW_S)

    if request.content_length and request.content_length > MAX_CONTENT_LENGTH:
        abort(413, description="Payload muito grande.")

    data = request.json or {}
    if not _validate_webhook_payload(data):
        return "Payload inválido", 400

    try:
        field, _ = parse_change(data)

        if field == "messages":
            handle_message_event(data)
            socketio.emit("new_message", redact_dict(data))

        elif field == "message_template_status_update":
            handle_status_event(data)
            socketio.emit("status_update", redact_dict(data))

    except Exception as e:
        print("Erro ao processar webhook:", e)
        return "Erro ao processar webhook", 500

    return "Evento recebido", 200


@realtime_bp.route("/")
@role_required("Admin", "Medico", "Atendente")
def realtime_dashboard():
    return render_template("realtime_dashboard.html")
