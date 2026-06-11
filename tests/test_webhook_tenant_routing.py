"""COM-3 — resolução de tenant por phone_number_id + HMAC por tenant (29.3 RM5).

Encerra o vazamento cross-tenant (toda mensagem caía na clínica default) e
valida a assinatura contra o app_secret do tenant resolvido.
"""
from __future__ import annotations

import hashlib
import hmac

from flask import Flask

import src.services.message_service as ms
import src.repositories.tenant_settings_repository as tsr
import src.services.tenant_secrets as tsec
import src.web.routes.realtime_notifications as realtime


# ── resolve_tenant_routing ────────────────────────────────────────────────

def test_routing_resolve_tenant_por_phone_number_id(monkeypatch):
    monkeypatch.setattr(
        tsr, "resolve_tenant_by_phone_number_id",
        lambda pnid: {"tenant_id": 7, "clinic_id": 42, "status": "active"},
    )
    out = ms.resolve_tenant_routing(
        {"metadata": {"phone_number_id": "PNID-1"}}, default_clinic_id=1
    )
    assert out == {"clinic_id": 42, "tenant_id": 7}


def test_routing_sem_phone_number_id_usa_default_sem_consultar_db(monkeypatch):
    chamadas = {"n": 0}
    monkeypatch.setattr(
        tsr, "resolve_tenant_by_phone_number_id",
        lambda pnid: chamadas.__setitem__("n", chamadas["n"] + 1) or None,
    )
    out = ms.resolve_tenant_routing({"metadata": {}}, default_clinic_id=9)
    assert out == {"clinic_id": 9, "tenant_id": None}
    assert chamadas["n"] == 0  # nem consulta o banco


def test_routing_sem_match_faz_fallback_default(monkeypatch):
    monkeypatch.setattr(tsr, "resolve_tenant_by_phone_number_id", lambda pnid: None)
    out = ms.resolve_tenant_routing(
        {"metadata": {"phone_number_id": "PNID-X"}}, default_clinic_id=3
    )
    assert out == {"clinic_id": 3, "tenant_id": None}


def test_routing_tenant_sem_legacy_clinic_cai_no_default(monkeypatch):
    monkeypatch.setattr(
        tsr, "resolve_tenant_by_phone_number_id",
        lambda pnid: {"tenant_id": 5, "clinic_id": None},
    )
    out = ms.resolve_tenant_routing(
        {"metadata": {"phone_number_id": "PNID-2"}}, default_clinic_id=8
    )
    assert out == {"clinic_id": 8, "tenant_id": 5}


# ── HMAC por tenant (integração no webhook) ───────────────────────────────

def _build_app() -> Flask:
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")
    app.register_blueprint(realtime.realtime_bp, url_prefix="/realtime")
    return app


def _payload_with_pnid() -> bytes:
    return (
        b'{"entry":[{"changes":[{"field":"messages","value":{'
        b'"metadata":{"phone_number_id":"PNID-TENANT"},'
        b'"messages":[{"id":"w1","from":"5511999999999","text":{"body":"oi"}}]}}]}]}'
    )


def test_webhook_valida_hmac_contra_segredo_do_tenant(monkeypatch):
    body = _payload_with_pnid()
    tenant_secret = "segredo-do-tenant"
    sig = hmac.new(tenant_secret.encode(), body, hashlib.sha256).hexdigest()
    processed = []

    monkeypatch.setenv("WHATSAPP_WEBHOOK_REQUIRE_SIGNATURE", "true")
    monkeypatch.setattr(realtime, "WHATSAPP_APP_SECRET", "segredo-global-diferente")
    monkeypatch.setattr(
        tsr, "resolve_tenant_by_phone_number_id",
        lambda pnid: {"tenant_id": 7, "clinic_id": 42},
    )
    monkeypatch.setattr(
        tsec, "get_whatsapp_config", lambda tenant_id=None: {"app_secret": tenant_secret}
    )
    monkeypatch.setattr(
        realtime, "_process_meta_payload", lambda data, clinic_id: processed.append(1)
    )

    resp = _build_app().test_client().post(
        "/realtime/webhook/meta", data=body, content_type="application/json",
        headers={"X-Hub-Signature-256": f"sha256={sig}", "X-Forwarded-For": "203.0.113.20"},
    )
    assert resp.status_code == 200
    assert processed == [1]


def test_webhook_rejeita_assinatura_com_segredo_global_quando_tenant_difere(monkeypatch):
    body = _payload_with_pnid()
    # Assina com o segredo GLOBAL, mas o tenant resolvido espera outro segredo.
    sig = hmac.new(b"segredo-global-diferente", body, hashlib.sha256).hexdigest()

    monkeypatch.setenv("WHATSAPP_WEBHOOK_REQUIRE_SIGNATURE", "true")
    monkeypatch.setattr(realtime, "WHATSAPP_APP_SECRET", "segredo-global-diferente")
    monkeypatch.setattr(
        tsr, "resolve_tenant_by_phone_number_id",
        lambda pnid: {"tenant_id": 7, "clinic_id": 42},
    )
    monkeypatch.setattr(
        tsec, "get_whatsapp_config", lambda tenant_id=None: {"app_secret": "segredo-do-tenant"}
    )

    resp = _build_app().test_client().post(
        "/realtime/webhook/meta", data=body, content_type="application/json",
        headers={"X-Hub-Signature-256": f"sha256={sig}", "X-Forwarded-For": "203.0.113.21"},
    )
    assert resp.status_code == 403
