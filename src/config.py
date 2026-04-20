# src/config.py

import os
from dotenv import load_dotenv

load_dotenv()

# ==============================
# BANCO DE DADOS
# ==============================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("A variável de ambiente DATABASE_URL não foi definida.")

DEFAULT_CLINIC_ID = int(os.getenv("DEFAULT_CLINIC_ID", "1"))

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
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGIN", "http://localhost:3000").split(",")
    if origin.strip()
]

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

# ==============================
# CHAT / INTAKE WEBSOCKET
# ==============================
CHAT_SESSION_TTL_S = int(os.getenv("CHAT_SESSION_TTL_S", "3600"))        # 1h padrão
CHAT_CLEANUP_INTERVAL_S = int(os.getenv("CHAT_CLEANUP_INTERVAL_S", "300"))  # 5min
TRIAGE_LINK_TTL_S = int(os.getenv("TRIAGE_LINK_TTL_S", "259200"))  # 72h

# ==============================
# TELEMETRIA PÓS-CONSULTA
# ==============================
TELEMETRY_FOLLOWUP_SEND_HOUR = int(os.getenv("TELEMETRY_FOLLOWUP_SEND_HOUR", "10"))  # 10h UTC
TELEMETRY_DISPATCH_INTERVAL_M = int(os.getenv("TELEMETRY_DISPATCH_INTERVAL_M", "15"))  # a cada 15min
TELEMETRY_IOT_BATCH_MAX = int(os.getenv("TELEMETRY_IOT_BATCH_MAX", "500"))
