from __future__ import annotations

from flask import Flask

import src.web.routes.realtime_notifications as realtime


def _build_app() -> Flask:
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")
    app.register_blueprint(realtime.realtime_bp, url_prefix="/realtime")
    return app


def test_twilio_webhook_skeleton_returns_501():
    resp = _build_app().test_client().post(
        "/realtime/webhook/twilio",
        data=b'{"any": "payload"}',
        content_type="application/json",
    )
    assert resp.status_code == 501


def test_zapi_webhook_skeleton_returns_501():
    resp = _build_app().test_client().post(
        "/realtime/webhook/zapi",
        data=b'{"any": "payload"}',
        content_type="application/json",
    )
    assert resp.status_code == 501
