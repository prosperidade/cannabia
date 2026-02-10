from flask import Blueprint, render_template, request
from flask_login import login_required
from flask_socketio import SocketIO

from config import VERIFY_TOKEN
from extensions import csrf
from services.message_service import handle_message_event, handle_status_event, parse_change

socketio = SocketIO()
realtime_bp = Blueprint('realtime', __name__, template_folder='templates')


@realtime_bp.route('/webhook', methods=['GET', 'POST'])
@csrf.exempt
def webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        if mode and token:
            if mode == 'subscribe' and token == VERIFY_TOKEN:
                return challenge, 200
            return 'Falha na verificação', 403
        return 'Parâmetros ausentes', 400

    data = request.json or {}
    field, _ = parse_change(data)

    try:
        if field == 'messages':
            handle_message_event(data)
            socketio.emit('new_message', data)
        elif field == 'message_template_status_update':
            handle_status_event(data)
            socketio.emit('status_update', data)
    except Exception as e:
        print('Erro ao processar webhook:', e)

    return 'Evento recebido', 200


@realtime_bp.route('/')
@login_required
def realtime_dashboard():
    return render_template('realtime_dashboard.html')
