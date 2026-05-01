from __future__ import annotations

from flask import Flask, g
from flask_login import LoginManager

from src.web.auth_identity import AppUser
from src.web.routes.telemetry import telemetry_bp


USER_ID = 44
CSRF_TOKEN = "test-csrf-token"


def _build_app(*, role: str = "Medico") -> Flask:
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
        g.tenant_id = 1

    app.register_blueprint(telemetry_bp)
    return app


def _client(app: Flask):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(USER_ID)
        sess["csrf_token"] = CSRF_TOKEN
    return client


def _headers() -> dict[str, str]:
    return {"Content-Type": "application/json", "X-CSRF-Token": CSRF_TOKEN}


def test_iot_ingest_requires_authentication():
    resp = _build_app().test_client().post("/api/telemetry/iot", json={})

    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "unauthenticated"


def test_iot_ingest_requires_csrf_for_authenticated_user():
    resp = _client(_build_app()).post("/api/telemetry/iot", json={})

    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "csrf_invalid"


def test_iot_ingest_authorized_with_csrf(monkeypatch):
    monkeypatch.setattr(
        "src.repositories.telemetry_repository.insert_iot_reading",
        lambda **_: 123,
    )

    resp = _client(_build_app()).post(
        "/api/telemetry/iot",
        json={
            "patient_id": 9,
            "source": "manual",
            "metric_type": "sleep_hours",
            "value": 7.5,
            "unit": "hours",
            "recorded_at": "2026-05-01T10:00:00Z",
        },
        headers=_headers(),
    )

    assert resp.status_code == 201
    assert resp.get_json()["id"] == 123


def test_iot_query_rejects_patient_role():
    resp = _client(_build_app(role="Paciente")).get(
        "/api/telemetry/iot/9?metric_type=sleep_hours&start=2026-05-01T00:00:00Z&end=2026-05-02T00:00:00Z"
    )

    assert resp.status_code == 403


def test_admin_schedule_requires_admin_role():
    resp = _client(_build_app(role="Medico")).post(
        "/api/telemetry/admin/schedule-now",
        json={},
        headers=_headers(),
    )

    assert resp.status_code == 403


def test_admin_schedule_allows_admin_clinica(monkeypatch):
    monkeypatch.setattr(
        "src.infra.telemetry_tasks.enqueue_schedule_daily_followups",
        lambda: "job-1",
    )

    resp = _client(_build_app(role="AdminClinica")).post(
        "/api/telemetry/admin/schedule-now",
        json={},
        headers=_headers(),
    )

    assert resp.status_code == 202
    assert resp.get_json()["job_id"] == "job-1"
