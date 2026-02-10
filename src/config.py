
import os
import json
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'root')
DB_NAME = os.getenv('DB_NAME', 'cannabia')

VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'SEU_VERIFY_TOKEN_PADRAO')
SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-prod')

APP_AUTH_USERNAME = os.getenv('APP_AUTH_USERNAME', 'admin')
APP_AUTH_PASSWORD = os.getenv('APP_AUTH_PASSWORD', 'admin123')



META_WHATSAPP_KEY = os.getenv('META_WHATSAPP_KEY')
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
RECIPIENT_PHONE = os.getenv('RECIPIENT_PHONE')

DOCTOR_EMAIL = os.getenv('DOCTOR_EMAIL')
EMAIL_FROM = os.getenv('EMAIL_FROM')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'true').lower() == 'true'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
PREFERRED_URL_SCHEME = 'https'

WEBHOOK_RATE_LIMIT = int(os.getenv('WEBHOOK_RATE_LIMIT', '60'))
WEBHOOK_RATE_WINDOW_S = int(os.getenv('WEBHOOK_RATE_WINDOW_S', '60'))
LOGIN_RATE_LIMIT = int(os.getenv('LOGIN_RATE_LIMIT', '10'))
LOGIN_RATE_WINDOW_S = int(os.getenv('LOGIN_RATE_WINDOW_S', '60'))
MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', str(256 * 1024)))

# JSON string: [{"username":"admin","password":"...","role":"Admin"}, ...]
DEFAULT_USERS = [
    {'username': 'admin', 'password': 'admin123', 'role': 'Admin'},
    {'username': 'medico', 'password': 'medico123', 'role': 'Medico'},
    {'username': 'atendente', 'password': 'atendente123', 'role': 'Atendente'},
]
USERS = json.loads(os.getenv('APP_USERS_JSON', json.dumps(DEFAULT_USERS)))

