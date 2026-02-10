import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import DOCTOR_EMAIL, EMAIL_FROM, EMAIL_PASSWORD


def send_email_notification(subject, message, to_email=None):
    to_email = to_email or DOCTOR_EMAIL

    if not (EMAIL_FROM and EMAIL_PASSWORD and to_email):
        print('Credenciais de e-mail não configuradas completamente.')
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_FROM
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print('Email enviado com sucesso!')
    except Exception as e:
        print('Erro ao enviar email:', e)
