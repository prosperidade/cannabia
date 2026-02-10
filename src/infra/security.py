import logging
import re

SENSITIVE_KEYS = {
    'authorization',
    'token',
    'verify_token',
    'meta_whatsapp_key',
    'email_password',
    'password',
    'secret',
}


def redact_text(value: str) -> str:
    if not value:
        return value
    value = re.sub(r'(Bearer\s+)[A-Za-z0-9._\-]+', r'\1***', value)
    value = re.sub(r'([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})', r'***@\2', value)
    value = re.sub(r'\b\d{8,15}\b', '***PHONE***', value)
    return value


def redact_dict(data):
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if str(k).lower() in SENSITIVE_KEYS:
                out[k] = '***REDACTED***'
            else:
                out[k] = redact_dict(v)
        return out
    if isinstance(data, list):
        return [redact_dict(i) for i in data]
    if isinstance(data, str):
        return redact_text(data)
    return data


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        record.msg = redact_text(str(record.msg))
        if record.args:
            record.args = tuple(redact_text(str(a)) for a in record.args)
        return super().format(record)
