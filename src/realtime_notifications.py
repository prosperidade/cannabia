
from flask_socketio import SocketIO
socketio = SocketIO()

from flask import Blueprint, render_template, request
from flask_socketio import emit
import mysql.connector
from mysql.connector import Error
from whatsapp_template import send_whatsapp_template
from notifications import send_email_notification
from dotenv import load_dotenv
import os

load_dotenv()

realtime_bp = Blueprint('realtime', __name__, template_folder='templates')

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "SEU_VERIFY_TOKEN_PADRAO")

def store_message_event(data):
    try:
        entry = data.get('entry', [])[0]['changes'][0]['value']
        messages = entry.get('messages', [])
        contacts = entry.get('contacts', [])
        if not messages:
            print("Nenhuma mensagem encontrada no payload.")
            return

        message = messages[0]
        sender = message.get('from', 'desconhecido')
        message_text = message.get('text', {}).get('body', '')
        timestamp = message.get('timestamp', '')
        contact_name = "desconhecido"
        if contacts:
            contact = contacts[0]
            contact_name = contact.get('profile', {}).get('name', 'desconhecido')

        print(f"Dados extraídos - Remetente: {sender}, Nome: {contact_name}, Mensagem: {message_text}, Timestamp: {timestamp}")

        connection = mysql.connector.connect(
            host='127.0.0.1', port=3306,
            user='root', password='root', database='cannabia'
        )
        cursor = connection.cursor()
        create_table_query = """
        CREATE TABLE IF NOT EXISTS incoming_messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            sender VARCHAR(50),
            contact_name VARCHAR(100),
            message_text TEXT,
            timestamp VARCHAR(50)
        )
        """
        cursor.execute(create_table_query)
        insert_query = """
        INSERT INTO incoming_messages (sender, contact_name, message_text, timestamp)
        VALUES (%s, %s, %s, %s)
        """
        cursor.execute(insert_query, (sender, contact_name, message_text, timestamp))
        connection.commit()
        cursor.close()
        connection.close()
        print("Mensagem armazenada com sucesso!")
    except Exception as e:
        print("Erro ao armazenar mensagem:", e)

def process_automatic_response(data):
    try:
        entry = data.get('entry', [])[0]['changes'][0]['value']
        messages = entry.get('messages', [])
        if not messages:
            print("Nenhuma mensagem para processar para resposta automática.")
            return
        message = messages[0]
        message_text = message.get('text', {}).get('body', '').lower()
        sender = message.get('from')
        resposta = None
        if "oi" in message_text or "olá" in message_text:
            resposta = "Olá! Como posso ajudar você hoje?"
        elif "td bem" in message_text or "tudo bem" in message_text:
            resposta = "Tudo ótimo, obrigado por perguntar!"
        if resposta:
            response = send_whatsapp_template(recipient_phone=sender, template_name="hello_world", language_code="en_US")
            print("Resposta automática enviada:", response)
        else:
            print("Nenhuma regra de resposta aplicável para:", message_text)
    except Exception as e:
        print("Erro ao processar resposta automática:", e)

def process_critical_notification(data):
    try:
        entry = data.get('entry', [])[0]['changes'][0]['value']
        messages = entry.get('messages', [])
        if not messages:
            return
        message = messages[0]
        message_text = message.get('text', {}).get('body', '').lower()
        if "ajuda" in message_text or "urgente" in message_text or "crítico" in message_text:
            subject = "Alerta Crítico no Sistema Cannab'IA"
            email_message = f"Uma mensagem crítica foi recebida:\n\n{message_text}"
            send_email_notification(subject, email_message)
    except Exception as e:
        print("Erro ao processar notificação crítica:", e)

def store_status_event(data):
    try:
        entry = data.get('entry', [])[0]['changes'][0]
        field = entry.get('field')
        if field != "message_template_status_update":
            print("Evento de status não identificado:", field)
            return
        value = entry.get('value', {})
        message_id = value.get('id', '')
        status = value.get('status', '')
        timestamp = value.get('timestamp', '')
        print(f"Status update - Message ID: {message_id}, Status: {status}, Timestamp: {timestamp}")
        connection = mysql.connector.connect(
            host='127.0.0.1', port=3306,
            user='root', password='root', database='cannabia'
        )
        cursor = connection.cursor()
        create_table_query = """
        CREATE TABLE IF NOT EXISTS message_status_updates (
            id INT AUTO_INCREMENT PRIMARY KEY,
            message_id VARCHAR(100),
            status VARCHAR(50),
            timestamp VARCHAR(50)
        )
        """
        cursor.execute(create_table_query)
        insert_query = """
        INSERT INTO message_status_updates (message_id, status, timestamp)
        VALUES (%s, %s, %s)
        """
        cursor.execute(insert_query, (message_id, status, timestamp))
        connection.commit()
        cursor.close()
        connection.close()
        print("Status de mensagem armazenado com sucesso!")
    except Exception as e:
        print("Erro ao armazenar status de mensagem:", e)

@realtime_bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode and token:
            if mode == 'subscribe' and token == VERIFY_TOKEN:
                print("Webhook verificado com sucesso")
                return challenge, 200
            else:
                return "Falha na verificação", 403
        else:
            return "Parâmetros ausentes", 400
    elif request.method == 'POST':
        data = request.json
        print("Evento recebido:", data)
        try:
            entry = data.get('entry', [])[0]['changes'][0]
            field = entry.get('field')
            if field == "messages":
                store_message_event(data)
                process_automatic_response(data)
                process_critical_notification(data)
                socketio.emit('new_message', data, broadcast=True)
            elif field == "message_template_status_update":
                store_status_event(data)
                socketio.emit('status_update', data, broadcast=True)
            else:
                print("Evento não processado:", field)
        except Exception as e:
            print("Erro ao processar evento:", e)
        return "Evento recebido", 200

@realtime_bp.route('/')
def realtime_dashboard():
    return render_template('realtime_dashboard.html')
