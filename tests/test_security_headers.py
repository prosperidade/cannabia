"""
SEC-1 (doc 30 Onda 1) — testes do helper de cabecalhos de seguranca.
"""

from __future__ import annotations

import pytest

from src.web.security_headers import apply_security_headers, DEFAULT_CSP


class _FakeResponse:
    """Stand-in minimo de flask.Response: so precisa de .headers com setdefault."""

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}


def _apply(**kwargs):
    resp = _FakeResponse()
    apply_security_headers(resp, **kwargs)
    return resp.headers


class TestStaticHeaders:
    def test_always_sets_nosniff_frame_referrer(self) -> None:
        h = _apply(is_secure=False)
        assert h["X-Content-Type-Options"] == "nosniff"
        assert h["X-Frame-Options"] == "DENY"
        assert h["Referrer-Policy"] == "no-referrer"


class TestHSTS:
    def test_hsts_only_when_secure(self) -> None:
        assert "Strict-Transport-Security" in _apply(is_secure=True)
        assert "Strict-Transport-Security" not in _apply(is_secure=False)

    def test_hsts_value(self) -> None:
        h = _apply(is_secure=True)
        assert "max-age=31536000" in h["Strict-Transport-Security"]
        assert "includeSubDomains" in h["Strict-Transport-Security"]


class TestCSP:
    def test_report_only_by_default(self) -> None:
        h = _apply(is_secure=False, csp_report_only=True)
        assert "Content-Security-Policy-Report-Only" in h
        assert "Content-Security-Policy" not in h  # nome exato do enforcing ausente

    def test_enforcing_when_not_report_only(self) -> None:
        h = _apply(is_secure=False, csp_report_only=False)
        assert h.get("Content-Security-Policy") == DEFAULT_CSP
        assert "Content-Security-Policy-Report-Only" not in h

    def test_custom_policy_used(self) -> None:
        policy = "default-src 'none'"
        h = _apply(is_secure=False, csp_report_only=False, csp_policy=policy)
        assert h["Content-Security-Policy"] == policy

    def test_default_csp_blocks_framing_and_objects(self) -> None:
        # garante que a politica default e defensiva
        assert "frame-ancestors 'none'" in DEFAULT_CSP
        assert "object-src 'none'" in DEFAULT_CSP


class TestKillSwitchAndSetdefault:
    def test_disabled_sets_nothing(self) -> None:
        h = _apply(is_secure=True, enabled=False)
        assert h == {}

    def test_does_not_overwrite_existing_header(self) -> None:
        resp = _FakeResponse()
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        apply_security_headers(resp, is_secure=False)
        assert resp.headers["X-Frame-Options"] == "SAMEORIGIN"

    def test_returns_response(self) -> None:
        resp = _FakeResponse()
        assert apply_security_headers(resp, is_secure=False) is resp
