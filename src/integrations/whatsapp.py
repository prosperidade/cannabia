import requests

from src.config import META_WHATSAPP_KEY, RECIPIENT_PHONE, WHATSAPP_PHONE_NUMBER_ID


def send_whatsapp_template(recipient_phone=None, template_name='hello_world', language_code='en_US'):
    recipient_phone = recipient_phone or RECIPIENT_PHONE

    if not META_WHATSAPP_KEY:
        raise ValueError('Token de acesso não encontrado. Verifique META_WHATSAPP_KEY no .env')
    if not WHATSAPP_PHONE_NUMBER_ID:
        raise ValueError('WHATSAPP_PHONE_NUMBER_ID não encontrado no .env')
    if not recipient_phone:
        raise ValueError('recipient_phone não informado e RECIPIENT_PHONE ausente no .env')

    url = f'https://graph.facebook.com/v22.0/{WHATSAPP_PHONE_NUMBER_ID}/messages'
    headers = {
        'Authorization': f'Bearer {META_WHATSAPP_KEY}',
        'Content-Type': 'application/json',
    }
    payload = {
        'messaging_product': 'whatsapp',
        'to': recipient_phone,
        'type': 'template',
        'template': {
            'name': template_name,
            'language': {'code': language_code},
        },
    }
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    return response.json()
