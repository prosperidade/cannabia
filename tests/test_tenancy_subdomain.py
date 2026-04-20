"""Testes da extracao de subdominio do Host header."""

from src.tenancy import _extract_subdomain


def test_extract_subdomain_basic():
    assert _extract_subdomain("verde-vida.cannabia.app") == "verde-vida"


def test_extract_subdomain_with_port():
    assert _extract_subdomain("verde-vida.cannabia.app:443") == "verde-vida"


def test_extract_subdomain_localhost_returns_none():
    assert _extract_subdomain("localhost") is None
    assert _extract_subdomain("localhost:3000") is None


def test_extract_subdomain_ip_returns_none():
    assert _extract_subdomain("192.168.1.1") is None


def test_extract_subdomain_apex_domain_returns_none():
    assert _extract_subdomain("cannabia.app") is None


def test_extract_subdomain_ignores_common_prefixes():
    assert _extract_subdomain("www.cannabia.app") is None
    assert _extract_subdomain("api.cannabia.app") is None
    assert _extract_subdomain("admin.cannabia.app") is None
    assert _extract_subdomain("app.cannabia.app") is None


def test_extract_subdomain_empty_returns_none():
    assert _extract_subdomain("") is None
    assert _extract_subdomain(None) is None


def test_extract_subdomain_case_insensitive():
    assert _extract_subdomain("Verde-Vida.Cannabia.App") == "verde-vida"
