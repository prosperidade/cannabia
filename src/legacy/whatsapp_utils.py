import os
import requests
from dotenv import load_dotenv, find_dotenv

# Carrega as variáveis do arquivo .env da raiz do projeto
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

ACCESS_TOKEN = os.getenv("META_WHATSAPP_KEY")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")  # Armazene o Phone Number ID também no .env

def send_whatsapp_template(recipient_phone: str, template_name: str = "hello_world", language_code: str = "en_US") -> dict:
    """
    Envia uma mensagem de template pelo WhatsApp Cloud API.
    
    :param recipient_phone: Número do destinatário em formato internacional (ex: "5562982810427")
    :param template_name: Nome do template a ser enviado (padrão: "hello_world")
    :param language_code: Código da linguagem, ex: "en_US"
    :return: Dicionário com a resposta da API
    """
    if not ACCESS_TOKEN:
        raise ValueError("Token de acesso não encontrado. Verifique sua variável META_WHATSAPP_KEY no .env")
    if not PHONE_NUMBER_ID:
        raise ValueError("Phone Number ID não encontrado. Defina a variável WHATSAPP_PHONE_NUMBER_ID no .env")
    
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code
            }
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

# Exemplo de uso direto do módulo
if __name__ == "__main__":
    # Altere para o número do destinatário desejado no formato internacional
    recipient = "5562982810427"
    result = send_whatsapp_template(recipient)
    print("Resultado:", result)
