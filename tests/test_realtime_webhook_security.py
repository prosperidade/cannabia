from __future__ import annotations

import hashlib
import hmac

from flask import Flask

import src.web.routes.realtime_notifications as realtime


def _build_app() -> Flask:
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")
    app.register_blueprint(realtime.realtime_bp, url_prefix="/realtime")
    return app


def _payload() -> bytes:
    return (
        b'{"entry":[{"changes":[{"field":"messages","value":{"messages":['
        b'{"from":"5511999999999","text":{"body":"oi"}}]}}]}]}'
    )


def test_meta_webhook_rejects_when_signature_required_without_secret(monkeypatch):
    monkeypatch.setenv("WHATSAPP_WEBHOOK_REQUIRE_SIGNATURE", "true")
    monkeypatch.setattr(realtime, "WHATSAPP_APP_SECRET", None)

    resp = _build_app().test_client().post(
        "/realtime/webhook/meta",
        data=_payload(),
        content_type="application/json",
        headers={"X-Forwarded-For": "203.0.113.10"},
    )

    assert resp.status_code == 403


def test_meta_webhook_allows_missing_secret_in_dev_mode(monkeypatch):
    processed = []

    monkeypatch.delenv("WHATSAPP_WEBHOOK_REQUIRE_SIGNATURE", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setattr(realtime, "WHATSAPP_APP_SECRET", None)
    monkeypatch.setattr(
        realtime,
        "_process_meta_payload",
        lambda data, clinic_id: processed.append((data, clinic_id)),
    )

    resp = _build_app().test_client().post(
        "/realtime/webhook/meta",
        data=_payload(),
        content_type="application/json",
        headers={"X-Forwarded-For": "203.0.113.11"},
    )

    assert resp.status_code == 200
    assert len(processed) == 1


def test_meta_webhook_accepts_valid_hmac_when_signature_required(monkeypatch):
    secret = "meta-webhook-secret"
    body = _payload()
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    processed = []

    monkeypatch.setenv("WHATSAPP_WEBHOOK_REQUIRE_SIGNATURE", "true")
    monkeypatch.setattr(realtime, "WHATSAPP_APP_SECRET", secret)
    monkeypatch.setattr(
        realtime,
        "_process_meta_payload",
        lambda data, clinic_id: processed.append((data, clinic_id)),
    )

    resp = _build_app().test_client().post(
        "/realtime/webhook/meta",
        data=body,
        content_type="application/json",
        headers={
            "X-Hub-Signature-256": f"sha256={signature}",
            "X-Forwarded-For": "203.0.113.12",
        },
    )

    assert resp.status_code == 200
    assert len(processed) == 1
