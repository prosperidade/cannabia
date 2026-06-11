"""
SEC-1 (doc 30 Onda 1) — Cabecalhos HTTP de seguranca.

Achado da faxina de branches (docs/FAXINA_BRANCHES.md): o `after_request` global
do app NAO definia nenhum header de seguranca. Este modulo concentra a logica
(pura e testavel) de aplicacao desses cabecalhos, chamada pelo after_request de
src/app.py.

Decisoes:
- X-Content-Type-Options, X-Frame-Options e Referrer-Policy sao sempre aplicados.
- Strict-Transport-Security (HSTS) so e enviado quando a conexao e segura
  (HTTPS/producao) — enviar HSTS sobre HTTP em dev e inutil e pode confundir.
- Content-Security-Policy comeca em modo REPORT-ONLY (default) para nao quebrar
  as paginas Jinja legadas (inline scripts/styles). Promover a enforcing
  (CSP_REPORT_ONLY=false) apos validar que nada quebra. Ver doc 30 SEC-1.
- Usa setdefault: nunca sobrescreve um header que uma rota tenha definido
  deliberadamente.
"""

from __future__ import annotations

from typing import Any

# CSP default conservadora, compativel com as paginas legadas (inline permitido).
# Em report-only nao bloqueia nada; ao promover, reavaliar 'unsafe-inline'.
DEFAULT_CSP = (
    "default-src 'self'; "
    "img-src 'self' data: https:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; "
    "font-src 'self' data: https:; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)

# Headers estaticos sempre aplicados (independente de TLS).
_STATIC_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}

_HSTS_VALUE = "max-age=31536000; includeSubDomains"


def apply_security_headers(
    response: Any,
    *,
    is_secure: bool,
    enabled: bool = True,
    csp_report_only: bool = True,
    csp_policy: str = DEFAULT_CSP,
) -> Any:
    """Aplica os cabecalhos de seguranca a `response` e o retorna.

    Args:
        response: objeto com `.headers` no estilo dict (Flask Response).
        is_secure: True quando a requisicao chegou por HTTPS / producao — controla HSTS.
        enabled: kill switch (SECURITY_HEADERS_ENABLED).
        csp_report_only: True => Content-Security-Policy-Report-Only (nao bloqueia).
        csp_policy: a politica CSP a aplicar.
    """
    if not enabled:
        return response

    for name, value in _STATIC_HEADERS.items():
        response.headers.setdefault(name, value)

    if is_secure:
        response.headers.setdefault("Strict-Transport-Security", _HSTS_VALUE)

    csp_header = (
        "Content-Security-Policy-Report-Only"
        if csp_report_only
        else "Content-Security-Policy"
    )
    response.headers.setdefault(csp_header, csp_policy)

    return response
