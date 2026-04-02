# src/web/routes/auth.py
import secrets
import time
from flask import abort, request, session

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
    if not is_rate_allowed(namespace, limit, window_s):
        abort(429, description="Muitas requisições. Tente novamente em instantes.")


def is_rate_allowed(namespace: str, limit: int, window_s: int) -> bool:
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    key = f"{namespace}:{ip}"
    return _allow_rate(key, limit, window_s)


def generate_csrf_token() -> str:
    token = secrets.token_urlsafe(32)
    session["_csrf_token"] = token
    return token


def issue_csrf_token(force_new: bool = False) -> str:
    token = None if force_new else (session.get("_csrf_token") or session.get("csrf_token"))
    if token:
        session["_csrf_token"] = token
        session["csrf_token"] = token
        return token

    token = generate_csrf_token()
    session["csrf_token"] = token
    return token


def validate_csrf_value(sent: str) -> bool:
    expected = (session.get("_csrf_token") or session.get("csrf_token") or "").strip()
    sent = (sent or "").strip()
    return bool(sent) and bool(expected) and secrets.compare_digest(sent, expected)


def validate_csrf_from_form() -> bool:
    sent = request.form.get("_csrf_token") or request.form.get("csrf_token") or ""
    return validate_csrf_value(sent)
