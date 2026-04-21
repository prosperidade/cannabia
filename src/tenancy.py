# src/tenancy.py

import logging
from typing import Optional

from flask import g, session, request, abort
from flask_login import current_user

from src.repositories.tenancy_repository import (
    resolve_default_clinic_id,
    get_user_membership,
)
from src.repositories.tenant_settings_repository import (
    get_branding,
    resolve_tenant_by_subdomain,
)

logger = logging.getLogger("cannabia.tenancy")


def _extract_subdomain(host: Optional[str]) -> Optional[str]:
    if not host:
        return None
    # Remove porta
    hostname = host.split(":")[0].lower()
    # Ignorar localhost/IPs
    if hostname in {"localhost", "127.0.0.1"} or hostname.replace(".", "").isdigit():
        return None
    parts = hostname.split(".")
    if len(parts) < 3:
        return None
    candidate = parts[0]
    if candidate in {"www", "app", "api", "admin"}:
        return None
    return candidate


def init_tenancy(app):

    # Rotas publicas — nao exigem autenticacao nem clinic_id
    PUBLIC_PREFIXES = (
        "/static",
        "/realtime/webhook",
        "/api/v1/payments/webhook",
        "/api/v1/public/",
    )
    PUBLIC_PATHS    = {"/login", "/logout"}

    @app.before_request
    def attach_clinic_context():

        # Libera rotas publicas (health check, webhooks, login/logout)
        if request.path.startswith(PUBLIC_PREFIXES) or request.path in PUBLIC_PATHS:
            return

        # Expose subdominio/brand ao contexto quando identificavel (mesmo sem login)
        subdomain = _extract_subdomain(request.host)
        if subdomain:
            try:
                tenant_by_sub = resolve_tenant_by_subdomain(subdomain)
            except Exception as exc:
                logger.debug("Falha ao resolver subdominio %s: %s", subdomain, exc)
                tenant_by_sub = None
            if tenant_by_sub:
                g.subdomain_tenant_id = tenant_by_sub.get("tenant_id")
                g.subdomain_clinic_id = tenant_by_sub.get("clinic_id")

        if not current_user.is_authenticated:
            return

        user_id = int(current_user.id)

        clinic_id = session.get("active_clinic_id")

        # Se nao houver clinica ativa na sessao, tenta subdomain, depois default do usuario
        if clinic_id is None:
            clinic_id = getattr(g, "subdomain_clinic_id", None) or resolve_default_clinic_id(user_id)

            if clinic_id is None:
                abort(403)

            session["active_clinic_id"] = clinic_id

        membership = get_user_membership(user_id, clinic_id)

        if membership is None:
            abort(403)

        # Anexa no contexto global da request
        g.clinic_id = membership["clinic_id"]
        g.clinic_role = membership.get("clinic_role") or membership.get("role")
        g.tenant_id = membership.get("tenant_id") or membership["clinic_id"]
        g.tenant_role = membership.get("tenant_role") or g.clinic_role
        g.tenant_type = membership.get("tenant_type") or "clinic"
        session["active_tenant_id"] = g.tenant_id

        # Branding resolvido para a request (opcional)
        try:
            branding = get_branding(g.tenant_id)
        except Exception:
            branding = None
        g.tenant_branding = branding or {}
