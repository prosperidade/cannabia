"""
Envio de e-mail com suporte a configuracao por tenant.

Quando `tenant_id` e fornecido, as credenciais SMTP sao resolvidas por tenant
com fallback para variaveis de ambiente globais.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from src.services.tenant_secrets import get_email_config

logger = logging.getLogger("cannabia.email")


def send_email_notification(
    subject: str,
    message: str,
    to_email: Optional[str] = None,
    *,
    tenant_id: Optional[int] = None,
) -> bool:
    cfg = get_email_config(tenant_id)

    to_email = to_email or cfg.get("doctor_email")

    if not (cfg.get("email_from") and cfg.get("email_password") and to_email):
        logger.warning("Credenciais de e-mail incompletas para tenant_id=%s", tenant_id)
        return False

    msg = MIMEMultipart()
    msg["From"] = cfg["email_from"]
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(message, "plain"))

    try:
        server = smtplib.SMTP(cfg["smtp_server"], int(cfg["smtp_port"]), timeout=15)
        server.starttls()
        server.login(cfg["email_from"], cfg["email_password"])
        server.send_message(msg)
        server.quit()
        logger.info("Email enviado para %s (tenant_id=%s)", to_email, tenant_id)
        return True
    except Exception as exc:
        logger.error("Erro ao enviar email para %s: %s", to_email, exc)
        return False
