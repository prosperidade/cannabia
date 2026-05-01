from __future__ import annotations

from flask import Flask, g
from flask_login import LoginManager

from src.web.auth_identity import AppUser
from src.web.routes.system import flags, system_bp


USER_ID = 77


def _build_app(*, role: str = "Admin") -> Flask:
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == str(USER_ID):
            return AppUser(user_id=USER_ID, username="dev", role=role)
        return None

    @app.before_request
    def inject_context():
        g.clinic_id = 1

    app.register_blueprint(system_bp)
    return app


def _client(app: Flask):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(USER_ID)
    return client


def test_system_flags_admin_can_list_flags():
    app = _build_app(role="Admin")
    resp = _client(app).get("/api/v1/system/flags")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert "flags" in payload
    assert "ai_enabled" in payload["flags"]


def test_system_flags_reject_non_admin():
    app = _build_app(role="Medico")
    resp = _client(app).get("/api/v1/system/flags")

    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "forbidden"


def test_system_flags_admin_can_set_and_clear_override():
    app = _build_app(role="Admin")
    client = _client(app)

    try:
        set_resp = client.put("/api/v1/system/flags/ai_enabled", json={"enabled": False})
        assert set_resp.status_code == 200
        assert set_resp.get_json()["source"] == "override"
        assert flags.is_enabled("ai_enabled") is False

        clear_resp = client.delete("/api/v1/system/flags/ai_enabled")
        assert clear_resp.status_code == 200
        assert clear_resp.get_json()["source"] != "override"
    finally:
        flags.clear_override("ai_enabled")
