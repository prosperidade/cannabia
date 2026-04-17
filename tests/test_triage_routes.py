from __future__ import annotations

from flask import Flask, g
from flask_login import LoginManager
import pytest

from src.web.auth_identity import AppUser
from src.web.routes.api_v1 import api_v1_bp


@pytest.fixture
def triage_staff_client():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
    )

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == "1":
            return AppUser(user_id=1, username="admin", role="Admin")
        return None

    app.register_blueprint(api_v1_bp)

    @app.before_request
    def inject_context():
        g.clinic_id = 1
        g.clinic_role = "Admin"
        g.user_id = "1"

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = "1"
            session["csrf_token"] = "test-csrf-token"
        yield client


def test_create_triage_link_requires_authenticated_clinic_context(triage_staff_client, monkeypatch):
    monkeypatch.setattr(
        "src.services.triage_link_service.issue_triage_link",
        lambda clinic_id: {
            "token": "signed-token",
            "url": "http://localhost:3000/triagem?token=signed-token",
            "clinic_id": clinic_id,
            "clinic_label": "Clinica #1",
            "issued_at": "2026-04-16T12:00:00+00:00",
            "expires_at": "2026-04-19T12:00:00+00:00",
        },
    )

    response = triage_staff_client.post(
        "/api/v1/intake/triage-link",
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": "test-csrf-token",
        },
        json={},
    )

    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["token"] == "signed-token"
    assert payload["clinic_id"] == 1


def test_public_triage_link_context_validates_token(client, monkeypatch):
    monkeypatch.setattr(
        "src.services.triage_link_service.resolve_triage_link_token",
        lambda token: {"clinic_id": 3, "clinic_label": "Clinica Verde"},
    )

    response = client.get("/api/v1/intake/triage-link?token=abc")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["clinic_id"] == 3
    assert payload["clinic_label"] == "Clinica Verde"


def test_public_triage_route_requires_secure_token(client):
    with client.session_transaction() as session:
        session["csrf_token"] = "test-csrf-token"

    response = client.post(
        "/api/v1/intake/triage",
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": "test-csrf-token",
        },
        json={"identificacao": {"patient_name": "Ana Souza", "age": 42}},
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["message"] == "Link de triagem ausente. Solicite um link seguro da clinica."


def test_public_triage_route_accepts_wizard_payload_with_valid_token(client, monkeypatch):
    with client.session_transaction() as session:
        session["csrf_token"] = "test-csrf-token"

    captured: dict = {}

    monkeypatch.setattr(
        "src.services.triage_link_service.resolve_triage_link_token",
        lambda token: {"clinic_id": 9, "clinic_label": "Clinica Segura"},
    )

    def fake_submit(payload, clinic_id, **kwargs):
        captured["payload"] = payload
        captured["clinic_id"] = clinic_id
        return {
            "report_id": 501,
            "patient_id": 99,
            "clinic_id": clinic_id,
            "patient_name": "Ana Souza",
            "status": "pending",
            "prescription_contract": {
                "ready": True,
                "readiness": "ready",
                "message": "Contrato pronto.",
                "required_fields": [],
                "missing_required_fields": [],
                "missing_optional_fields": [],
                "resolved_values": {},
                "source_map": {},
                "report_id": 501,
                "patient_id": 99,
            },
        }

    monkeypatch.setattr("src.services.triage_intake_service.submit_triage_intake", fake_submit)

    response = client.post(
        "/api/v1/intake/triage",
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": "test-csrf-token",
        },
        json={
            "intake_token": "signed-token",
            "identificacao": {"patient_name": "Ana Souza", "age": 42},
            "motivo": {"objetivo_principal": "controle_ansiedade"},
            "sintomas": [{"intensidade": 8}],
            "dados_fisicos": {"peso_kg": 62, "altura_cm": 168, "sexo_biologico": "feminino"},
            "estado_emocional": {},
            "habitos": {"ja_usou_cannabis": True},
            "historico": {},
        },
    )

    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["report_id"] == 501
    assert payload["prescription_contract"]["ready"] is True
    assert captured["clinic_id"] == 9
