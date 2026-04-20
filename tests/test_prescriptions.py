from __future__ import annotations

from flask import Flask
from flask_login import LoginManager
import pytest

from src.web.auth_identity import AppUser
from src.web.routes.prescriptions import prescriptions_bp
from src.services.prescription_contract import PrescriptionContractError


@pytest.fixture
def prescriptions_client():
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

    app.register_blueprint(prescriptions_bp)

    @app.before_request
    def inject_context():
        from flask import g

        g.clinic_id = 1
        g.user_id = "1"

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = "1"
            session["csrf_token"] = "test-csrf-token"
        yield client


def test_calculate_dosage_returns_contract_details_on_incomplete_payload(prescriptions_client, monkeypatch):
    def fake_calculate(payload):
        raise PrescriptionContractError(
            "Prescrição segura ainda exige: Peso (kg).",
            {
                "ready": False,
                "message": "Prescrição segura ainda exige: Peso (kg).",
                "missing_required_fields": [{"field": "weight_kg", "label": "Peso (kg)"}],
                "missing_optional_fields": [],
                "required_fields": [],
                "resolved_values": {},
                "source_map": {},
                "readiness": "missing_required",
                "report_id": 10,
                "patient_id": 11,
            },
        )

    monkeypatch.setattr("src.web.routes.prescriptions._service.calculate_dosage", fake_calculate)

    response = prescriptions_client.post(
        "/api/v1/prescriptions/calculate",
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": "test-csrf-token",
        },
        json={"attendance_id": 10},
    )

    assert response.status_code == 422
    payload = response.get_json()["error"]
    assert payload["code"] == "prescription_contract_incomplete"
    assert payload["details"]["missing_required_fields"][0]["field"] == "weight_kg"


def test_calculate_dosage_returns_preview_payload(prescriptions_client, monkeypatch):
    monkeypatch.setattr(
        "src.web.routes.prescriptions._service.calculate_dosage",
        lambda payload: {
            "dosage_input": {"weight_kg": 60, "height_cm": 170, "prior_cannabis_use": False},
            "prescription_contract": {"ready": True},
            "recommendation": {"cannabinoid_ratio": "20:1"},
            "safety_limits": {"max_daily_mg": 40},
        },
    )

    response = prescriptions_client.post(
        "/api/v1/prescriptions/calculate",
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": "test-csrf-token",
        },
        json={"attendance_id": 10, "weight_kg": 60, "height_cm": 170, "prior_cannabis_use": False},
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["recommendation"]["cannabinoid_ratio"] == "20:1"
    assert payload["dosage_input"]["height_cm"] == 170


def test_emit_prescription_accepts_prescriber_payload(prescriptions_client, monkeypatch):
    monkeypatch.setattr(
        "src.web.routes.prescriptions._service.emit_prescription",
        lambda payload: {"prescription_id": 99, "status": "active"},
    )

    response = prescriptions_client.post(
        "/api/v1/prescriptions/emit",
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": "test-csrf-token",
        },
        json={
            "patient_id": 7,
            "doctor_user_id": 1,
            "doctor_name": "Dra. Maria",
            "doctor_crm": "12345",
            "dosage_recommendation": {
                "cannabinoid_ratio": "20:1",
                "spectrum": "full_spectrum",
                "administration_route": "sublingual",
                "concentration_mg_ml": 50,
                "titration_protocol": [
                    {
                        "phase": "inicial",
                        "day_range": "Dias 1-7",
                        "drops_per_dose": 2,
                        "doses_per_day": 2,
                        "concentration_mg_ml": 50,
                        "total_daily_mg": 10,
                    }
                ],
                "max_daily_mg": 40,
                "clinical_rationale": "Inicio baixo e titulacao gradual.",
                "contraindications": [],
                "drug_interactions": [],
                "monitoring_checkpoints": ["7 dias: tolerancia"],
                "confidence_score": 0.84,
                "evidence_sources": [],
            },
            "custom_notes": "Monitorar sonolencia.",
            "validity_days": 180,
        },
    )

    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["prescription_id"] == 99
    assert payload["status"] == "active"
