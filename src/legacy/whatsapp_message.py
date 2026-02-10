import os
import requests
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

# Recupera o token de acesso do arquivo .env
access_token = os.getenv("META_WHATSAPP_KEY")
if not access_token:
    raise ValueError("Token de acesso não encontrado no .env")

# Número do telefone fornecido pela sandbox (Phone Number ID)
phone_number_id = "561626383706776"

# Atualize o campo "to" com o número de telefone do destinatário no formato internacional, sem espaços ou +
recipient_phone = "15556330521"

url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

payload = {
    "messaging_product": "whatsapp",
    "to": recipient_phone,
    "type": "template",
    "template": {
        "name": "hello_world",
        "language": {
            "code": "en_US"
        }
    }
}

response = requests.post(url, headers=headers, json=payload)

print("Status Code:", response.status_code)
print("Response:", response.text)

