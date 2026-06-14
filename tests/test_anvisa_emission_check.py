"""CLI-3 — check_anvisa no caminho de emissão (29.2 R3 / A5).

Decisão registrada: *warning auditado*, NÃO bloqueante — o médico é o decisor e
a aprovação regulatória é prerrogativa da Anvisa.
"""
from __future__ import annotations

from flask import Flask, g

import src.infra.audit as audit_mod
import src.services.prescription_service as psvc
from src.ai.agents.regulatorio import check_anvisa
from src.services.prescription_service import PrescriptionService


# ── check_anvisa (unidade) ────────────────────────────────────────────────

def test_check_anvisa_via_inalatoria_nao_compliant():
    out = check_anvisa({"cannabinoid_ratio": "1:1", "administration_route": "inalatorio", "max_daily_mg": 20})
    assert out["compliant"] is False
    assert any("inalat" in i.lower() for i in out["issues"])


def test_check_anvisa_thc_alto_nao_compliant():
    out = check_anvisa({"cannabinoid_ratio": "thc rico", "administration_route": "oral", "max_daily_mg": 50})
    assert out["compliant"] is False


def test_check_anvisa_caso_conforme():
    out = check_anvisa({"cannabinoid_ratio": "20:1", "administration_route": "sublingual", "max_daily_mg": 40})
    assert out["compliant"] is True
    assert out["issues"] == []


# ── emit_prescription (integração: não bloqueia, audita) ──────────────────

def _emit_data(route: str = "inalatorio") -> dict:
    return {
        "patient_id": 7,
        "doctor_user_id": 1,
        "doctor_name": "Dra. Maria",
        "doctor_crm": "12345",
        "dosage_recommendation": {
            "cannabinoid_ratio": "1:1",
            "spectrum": "full_spectrum",
            "administration_route": route,
            "concentration_mg_ml": 50,
            "titration_protocol": [{
                "phase": "inicial", "day_range": "Dias 1-7", "drops_per_dose": 2,
                "doses_per_day": 2, "concentration_mg_ml": 50, "total_daily_mg": 10,
            }],
            "max_daily_mg": 40,
            "clinical_rationale": "Inicio baixo e titulacao gradual.",
            "contraindications": [],
            "drug_interactions": [],
            "monitoring_checkpoints": ["7 dias: tolerancia"],
            "confidence_score": 0.84,
            "evidence_sources": [],
        },
        "custom_notes": "n",
        "validity_days": 180,
    }


def test_emit_audita_alerta_anvisa_sem_bloquear(monkeypatch):
    monkeypatch.setattr(psvc, "_save_prescription", lambda **k: 99)
    audited = []
    monkeypatch.setattr(audit_mod, "log_audit_event", lambda **k: audited.append(k))

    app = Flask(__name__)
    with app.test_request_context():
        g.clinic_id = 1
        result = PrescriptionService().emit_prescription(_emit_data("inalatorio"))

    assert result["prescription_id"] == 99          # emitiu — NÃO bloqueou
    assert result["status"] == "active"
    assert result["anvisa_compliance"]["compliant"] is False
    assert audited and audited[0]["action"] == "prescription_anvisa_warning"
    assert audited[0]["resource_id"] == "99"


def test_emit_conforme_nao_audita(monkeypatch):
    monkeypatch.setattr(psvc, "_save_prescription", lambda **k: 100)
    audited = []
    monkeypatch.setattr(audit_mod, "log_audit_event", lambda **k: audited.append(k))

    app = Flask(__name__)
    with app.test_request_context():
        g.clinic_id = 1
        result = PrescriptionService().emit_prescription(_emit_data("sublingual"))

    assert result["prescription_id"] == 100
    assert result["anvisa_compliance"]["compliant"] is True
    assert audited == []
