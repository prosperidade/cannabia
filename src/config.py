# src/config.py

import logging
import os
import secrets

from dotenv import load_dotenv

load_dotenv()

_logger = logging.getLogger("cannabia.config")


def _get_secret_key_or_fail() -> str:
    """Resolve SECRET_KEY com estratégia híbrida FLASK_ENV-aware (Q-A3 / A.4).

    Producao (FLASK_ENV=production): raise se ausente — fallback hardcoded
    e' inaceitavel quando cookies/sessoes carregam dados sensiveis.

    Dev: gera chave random in-memory + warning. App sobe out-of-the-box;
    cookies invalidam a cada restart, mas isso e' ok em dev.
    """
    key = os.getenv("SECRET_KEY", "").strip()
    if key:
        return key
    if os.getenv("FLASK_ENV", "").lower() == "production":
        raise RuntimeError(
            "SECRET_KEY env var required in production. "
            "Render: gerar via dashboard ou usar render.yaml generateValue:true."
        )
    fallback = secrets.token_hex(32)
    _logger.warning(
        "SECRET_KEY ausente em ambiente non-production. Usando chave random "
        "em-memoria — cookies invalidam a cada restart. Setar SECRET_KEY no "
        ".env para sessoes persistentes em dev."
    )
    return fallback


def _get_sentry_config() -> dict | None:
    """Resolve config Sentry — pattern HARD em prod (Sprint 3 Track Obs-Harden).

    Decisao do coordenador (Q-OH-1, supersede Q-Obs-1): se SENTRY_DSN ausente
    em producao, RAISE direto — alinhado ao pattern A.4 (`_get_secret_key_or_fail`).
    Soft-fail Sprint 2 era pra nao bloquear rollout inicial; agora que
    Sentry esta integrado e validado, observabilidade em prod e' MANDATORY.

    Em dev (FLASK_ENV != production), DSN ausente continua silent (debug log) —
    desenvolvedor local nao precisa configurar Sentry.

    Returns:
        dict com {dsn, environment, sample_rate, traces_sample_rate} ou
        None se DSN ausente em dev (sinaliza pra init_sentry pular init).

    Raises:
        RuntimeError: se FLASK_ENV=production e SENTRY_DSN ausente.
    """
    dsn = os.getenv("SENTRY_DSN", "").strip()
    is_production = os.getenv("FLASK_ENV", "").lower() == "production"

    if not dsn:
        if is_production:
            raise RuntimeError(
                "SENTRY_DSN env var required in production. "
                "Setar no Render dashboard antes do deploy."
            )
        _logger.debug("SENTRY_DSN ausente em dev — Sentry off (esperado).")
        return None

    environment = os.getenv("SENTRY_ENVIRONMENT") or os.getenv("FLASK_ENV") or "development"

    sample_rate_default = "1.0" if is_production else "0.0"
    try:
        sample_rate = float(os.getenv("SENTRY_SAMPLE_RATE", sample_rate_default))
    except ValueError:
        _logger.warning(
            "SENTRY_SAMPLE_RATE invalido (%s) — usando default %s",
            os.getenv("SENTRY_SAMPLE_RATE"),
            sample_rate_default,
        )
        sample_rate = float(sample_rate_default)

    # Q-OH-2: traces_sample_rate default 0.1 (10% — Sprint 3 piloto).
    # Clamp 0.0..1.0 pra evitar valores absurdos quebrando o SDK.
    traces_default = "0.1"
    try:
        traces_sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", traces_default))
    except ValueError:
        _logger.warning(
            "SENTRY_TRACES_SAMPLE_RATE invalido (%s) — usando default %s",
            os.getenv("SENTRY_TRACES_SAMPLE_RATE"),
            traces_default,
        )
        traces_sample_rate = float(traces_default)
    traces_sample_rate = max(0.0, min(1.0, traces_sample_rate))

    return {
        "dsn": dsn,
        "environment": environment,
        "sample_rate": sample_rate,
        "traces_sample_rate": traces_sample_rate,
    }


def _check_encryption_key_or_fail() -> None:
    """Q-A5 / A.4: produção exige ENCRYPTION_KEY explícita.

    src/infra/crypto.py usa SECRET_KEY como seed HKDF se ENCRYPTION_KEY
    ausente — fallback dev-only. Em prod, rotacionar SECRET_KEY (pra
    invalidar sessoes) NAO deve invalidar ciphertexts em colunas
    _encrypted; por isso a chave de cripto precisa ser separada.
    """
    if os.getenv("FLASK_ENV", "").lower() == "production":
        if not os.getenv("ENCRYPTION_KEY"):
            raise RuntimeError(
                "ENCRYPTION_KEY env var required in production. "
                "Render: gerar via dashboard ou usar render.yaml "
                "generateValue:true. Nao usar SECRET_KEY como seed em prod."
            )

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
SECRET_KEY = _get_secret_key_or_fail()
_check_encryption_key_or_fail()

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
