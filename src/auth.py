import time
from functools import wraps

from flask import abort, redirect, request, session, url_for

# Rate limit simples em memória (por processo)
_RATE_BUCKET = {}


def _allow_rate(key: str, limit: int, window_s: int) -> bool:
    now = int(time.time())
    start = now - window_s
    entries = _RATE_BUCKET.get(key, [])
    entries = [t for t in entries if t > start]
    if len(entries) >= limit:
        _RATE_BUCKET[key] = entries
        return False
    entries.append(now)
    _RATE_BUCKET[key] = entries
    return True


def limit_or_429(namespace: str, limit: int, window_s: int):
    ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
    key = f'{namespace}:{ip}'
    if not _allow_rate(key, limit, window_s):
        abort(429, description='Muitas requisições. Tente novamente em instantes.')


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login', next=request.path))
        return fn(*args, **kwargs)

    return wrapper


def role_required(*allowed_roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get('user_id'):
                return redirect(url_for('login', next=request.path))
            role = session.get('role')
            if role not in allowed_roles:
                abort(403, description='Sem permissão para acessar este recurso.')
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def generate_csrf_token():
    import secrets

    token = secrets.token_urlsafe(32)
    session['_csrf_token'] = token
    return token


def validate_csrf_from_form() -> bool:
    sent = request.form.get('_csrf_token')
    expected = session.get('_csrf_token')
    return bool(sent and expected and sent == expected)
