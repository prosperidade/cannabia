# src/config.py

import os
from dotenv import load_dotenv

load_dotenv()

# ==============================
# BANCO DE DADOS
# Render injeta DATABASE_URL para bancos gerenciados.
# Fallback para variáveis individuais em dev local.
# ==============================
_DATABASE_URL = os.getenv("DATABASE_URL", "")

if _DATABASE_URL:
    # Render injection uses postgres:// natively, but SQLAlchemy expects postgresql://
    # Psycopg2 parses postgres:// and postgresql:// equally.
    DATABASE_URL = _DATABASE_URL
else:
    DB_HOST     = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT     = os.getenv("DB_PORT", "5432")
    DB_USER     = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
    DB_NAME     = os.getenv("DB_NAME", "cannabia")
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ══════════════════════════════
# IA / APIs
# ══════════════════════════════
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

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
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET")
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
