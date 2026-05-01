from __future__ import annotations

import hashlib
import hmac

from flask import Flask

from src.web.routes.payments import payments_bp


def _build_app() -> Flask:
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")
    app.register_blueprint(payments_bp)
    return app


def test_webhook_rejects_unsigned_when_signature_required(monkeypatch):
    monkeypatch.setenv("PAYMENT_WEBHOOK_REQUIRE_SIGNATURE", "true")
    monkeypatch.delenv("PAYMENT_WEBHOOK_SECRET_ASAAS", raising=False)
    monkeypatch.setattr("src.repositories.payment_repository.log_webhook", lambda **_: None)

    resp = _build_app().test_client().post(
        "/api/v1/payments/webhook/asaas",
        json={"external_id": "tx-1", "amount_cents": 1000},
    )

    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "invalid_signature"


def test_webhook_accepts_valid_signature_when_required(monkeypatch):
    secret = "webhook-secret"
    body = b'{"external_id":"tx-1","amount_cents":1000}'
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    monkeypatch.setenv("PAYMENT_WEBHOOK_REQUIRE_SIGNATURE", "true")
    monkeypatch.setenv("PAYMENT_WEBHOOK_SECRET_ASAAS", secret)
    monkeypatch.setattr("src.repositories.payment_repository.log_webhook", lambda **_: None)
    monkeypatch.setattr(
        "src.services.payment_service.process_webhook_event",
        lambda **_: {"processed": True},
    )

    resp = _build_app().test_client().post(
        "/api/v1/payments/webhook/asaas",
        data=body,
        content_type="application/json",
        headers={"X-Signature": signature},
    )

    assert resp.status_code == 200
    assert resp.get_json()["data"] == {"processed": True}
