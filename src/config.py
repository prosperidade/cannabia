# src/config.py

import os
from dotenv import load_dotenv

load_dotenv()

# ==============================
# BANCO DE DADOS
# ==============================
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
DB_NAME = os.getenv("DB_NAME", "cannabia")

# ==============================
# SEGURANÇA
# ==============================
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-fallback")

SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")

MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(1024 * 1024)))  # 1MB

# ==============================
# WHATSAPP / META
# ==============================
META_WHATSAPP_KEY = os.getenv("META_WHATSAPP_KEY")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
RECIPIENT_PHONE = os.getenv("RECIPIENT_PHONE")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "verify-token-dev")

# ==============================
# EMAIL
# ==============================
DOCTOR_EMAIL = os.getenv("DOCTOR_EMAIL")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

# ==============================
# RATE LIMIT
# ==============================
WEBHOOK_RATE_LIMIT = int(os.getenv("WEBHOOK_RATE_LIMIT", "60"))
WEBHOOK_RATE_WINDOW_S = int(os.getenv("WEBHOOK_RATE_WINDOW_S", "60"))

LOGIN_RATE_LIMIT = int(os.getenv("LOGIN_RATE_LIMIT", "10"))
LOGIN_RATE_WINDOW_S = int(os.getenv("LOGIN_RATE_WINDOW_S", "60"))
