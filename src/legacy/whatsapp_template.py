from integrations.whatsapp import send_whatsapp_template

__all__ = ['send_whatsapp_template']


if __name__ == '__main__':
    result = send_whatsapp_template()
    print('Resultado:', result)
