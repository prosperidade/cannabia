"""
Tests do A.4 — hardening (Sprint 1 Track A).

Cobre:
- _validate_next_url (src/app.py): open redirect + header injection.
- _get_secret_key_or_fail (src/config.py): Q-A3 estrategia (c) hibrida.
- _check_encryption_key_or_fail (src/config.py): Q-A5 prod-only check.
"""
from __future__ import annotations

import logging

import pytest


# =====================================================
# next_url validation — open redirect + header injection
# =====================================================

@pytest.mark.parametrize(
    "dangerous",
    [
        "https://evil.com/",
        "//evil.com/path",          # protocol-relative
        "http://other.com/",
        "javascript:alert(1)",       # nao comeca com '/'
        "\\evil.com",                # backslash
        "ftp://server/",
        None,
        "",
        "relative/path",             # nao comeca com '/'
    ],
)
def test_validate_next_url_blocks_open_redirect(dangerous):
    """A.4: open redirect e variantes de URL absoluta sao bloqueadas."""
    from src.app import _validate_next_url
    assert _validate_next_url(dangerous) is None, (
        f"esperado bloqueio pra {dangerous!r}"
    )


@pytest.mark.parametrize(
    "injection",
    [
        "/dashboard\nLocation: evil.com",
        "/dashboard\rContent-Type: application/x",
        "/dashboard\r\nX-Foo: bar",
        "/admin\nSet-Cookie: pwned=1",
    ],
)
def test_validate_next_url_blocks_header_injection(injection):
    """A.4: CR/LF em next_url permitiria HTTP header injection — bloqueado."""
    from src.app import _validate_next_url
    assert _validate_next_url(injection) is None, (
        f"esperado bloqueio pra {injection!r}"
    )


@pytest.mark.parametrize(
    "safe",
    [
        "/dashboard",
        "/p/consultas",
        "/admin/sistema",
        "/org/acompanhamento?id=42",
        "/med/dashboard#section",
    ],
)
def test_validate_next_url_allows_safe_relative_paths(safe):
    """Sanity: paths relativos legitimos passam intactos."""
    from src.app import _validate_next_url
    assert _validate_next_url(safe) == safe


# =====================================================
# SECRET_KEY failsafe — Q-A3 strategy (c) hibrida
# =====================================================

def test_secret_key_required_in_production(monkeypatch):
    """Q-A3 (c): producao com SECRET_KEY ausente -> RuntimeError."""
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    from src.config import _get_secret_key_or_fail

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _get_secret_key_or_fail()


def test_secret_key_random_fallback_in_dev(monkeypatch, caplog):
    """Q-A3 (c): non-production com SECRET_KEY ausente -> random + warning."""
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    from src.config import _get_secret_key_or_fail

    with caplog.at_level(logging.WARNING, logger="cannabia.config"):
        key = _get_secret_key_or_fail()

    # token_hex(32) -> 64 hex chars
    assert len(key) == 64, f"esperado token_hex(32)=64 chars, recebido {len(key)}"
    assert all(c in "0123456789abcdef" for c in key), "esperado hex puro"
    assert any(
        "SECRET_KEY ausente" in rec.message for rec in caplog.records
    ), "warning de SECRET_KEY ausente nao foi logado"


# =====================================================
# ENCRYPTION_KEY check — Q-A5 prod-only
# =====================================================

def test_encryption_key_required_in_production(monkeypatch):
    """Q-A5: producao sem ENCRYPTION_KEY -> RuntimeError."""
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)

    from src.config import _check_encryption_key_or_fail

    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
        _check_encryption_key_or_fail()
