import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'root')
DB_NAME = os.getenv('DB_NAME', 'cannabia')

VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'SEU_VERIFY_TOKEN_PADRAO')
SECRET_KEY = os.getenv('SECRET_KEY', 'secret!')

META_WHATSAPP_KEY = os.getenv('META_WHATSAPP_KEY')
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
RECIPIENT_PHONE = os.getenv('RECIPIENT_PHONE')

DOCTOR_EMAIL = os.getenv('DOCTOR_EMAIL')
EMAIL_FROM = os.getenv('EMAIL_FROM')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
