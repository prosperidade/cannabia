import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv, find_dotenv

# Carrega as variáveis do arquivo .env
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

DOCTOR_EMAIL = os.getenv("DOCTOR_EMAIL")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

def send_email_notification(subject, message, to_email=None):
    """
    Envia uma notificação por e-mail.
    :param subject: Assunto do e-mail.
    :param message: Conteúdo da mensagem.
    :param to_email: E-mail do destinatário (se não informado, usa DOCTOR_EMAIL do .env).
    :return: None.
    """
    if not to_email:
        to_email = DOCTOR_EMAIL
    if not (EMAIL_FROM and EMAIL_PASSWORD):
        print("Credenciais de e-mail não configuradas.")
        return

    # Configurações SMTP para Gmail (ajuste se usar outro provedor)
    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(message, "plain"))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Email enviado com sucesso!")
    except Exception as e:
        print("Erro ao enviar email:", e)
