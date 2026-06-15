"""REG-3 — condição grave/debilitante / cuidados paliativos (RDCs 2026).

Campo estruturado + justificativa do médico, auditado. NUNCA bloqueia
emissão (B6): a falta de condição habilitante em prescrição com THC vira
*warning auditado*, não impedimento.
"""
from __future__ import annotations

import pytest
from flask import Flask, g

import src.infra.audit as audit_mod
import src.services.prescription_service as psvc
from src.ai.schemas import DosageInput, RegulatoryCondition
from src.services.prescription_contract import build_prescription_contract
from src.services.prescription_service import PrescriptionService


# ── Schema ────────────────────────────────────────────────────────────────

def _dosage_input(**over):
    base = dict(
        patient_name="Ana", age=40, weight_kg=70.0,
        main_complaint="dor", symptoms=["dor"],
    )
    base.update(over)
    return DosageInput(**base)


def test_dosage_input_default_nenhuma():
    assert _dosage_input().regulatory_condition is RegulatoryCondition.NENHUMA


def test_dosage_input_aceita_grave_e_paliativa():
    assert _dosage_input(regulatory_condition="grave_debilitante").regulatory_condition \
        is RegulatoryCondition.GRAVE_DEBILITANTE
    assert _dosage_input(regulatory_condition="paliativa").regulatory_condition \
        is RegulatoryCondition.PALIATIVA


def test_dosage_input_rejeita_valor_invalido():
    with pytest.raises(Exception):
        _dosage_input(regulatory_condition="inventada")


# ── Contrato de prescrição ────────────────────────────────────────────────

def test_contrato_resolve_condicao_de_override():
    c = build_prescription_contract(overrides={"regulatory_condition": "paliativa"})
    assert c["resolved_values"]["regulatory_condition"] == "paliativa"


def test_contrato_ignora_condicao_invalida():
    c = build_prescription_contract(overrides={"regulatory_condition": "xpto"})
    assert "regulatory_condition" not in c["resolved_values"]


# ── emit_prescription (não bloqueia; audita justificativa) ─────────────────

def _emit_data(ratio="1:1", route="sublingual", **extra):
    data = {
        "patient_id": 7, "doctor_user_id": 1, "doctor_name": "Dra. Maria",
        "doctor_crm": "12345",
        "dosage_recommendation": {
            "cannabinoid_ratio": ratio, "spectrum": "full_spectrum",
            "administration_route": route, "concentration_mg_ml": 50,
            "titration_protocol": [{
                "phase": "inicial", "day_range": "Dias 1-7", "drops_per_dose": 2,
                "doses_per_day": 2, "concentration_mg_ml": 50, "total_daily_mg": 10,
            }],
            "max_daily_mg": 40, "clinical_rationale": "Titulacao gradual.",
            "contraindications": [], "drug_interactions": [],
            "monitoring_checkpoints": ["7 dias"], "confidence_score": 0.8,
            "evidence_sources": [],
        },
        "custom_notes": None, "validity_days": 180,
    }
    data.update(extra)
    return data


def _run_emit(monkeypatch, data):
    captured: dict = {}

    def fake_save(**k):
        captured.update(k)
        return 55

    monkeypatch.setattr(psvc, "_save_prescription", fake_save)
    audited: list = []
    monkeypatch.setattr(audit_mod, "log_audit_event", lambda **k: audited.append(k))

    app = Flask(__name__)
    with app.test_request_context():
        g.clinic_id = 1
        result = PrescriptionService().emit_prescription(data)
    return result, captured, audited


def test_emit_persiste_condicao_e_justificativa(monkeypatch):
    result, captured, audited = _run_emit(
        monkeypatch,
        _emit_data(
            regulatory_condition="grave_debilitante",
            clinical_justification="Paciente oncologico em dor refrataria.",
        ),
    )
    assert result["prescription_id"] == 55                       # emitiu
    assert captured["regulatory_condition"] == "grave_debilitante"
    assert "oncologico" in captured["clinical_justification"]
    assert result["reg_3"]["regulatory_condition"] == "grave_debilitante"
    assert result["reg_3"]["has_justification"] is True
    assert "prescription_regulatory_condition" in [a["action"] for a in audited]


def test_emit_thc_sem_condicao_audita_warning_sem_bloquear(monkeypatch):
    # ratio com THC, sem condição habilitante -> warning auditado, NÃO bloqueia.
    result, _captured, audited = _run_emit(monkeypatch, _emit_data(ratio="1:1"))
    assert result["prescription_id"] == 55                       # emitiu mesmo assim
    assert result["reg_3"].get("warning")
    assert "prescription_regulatory_condition_missing" in [a["action"] for a in audited]


def test_emit_cbd_puro_nao_dispara_reg3(monkeypatch):
    result, _captured, audited = _run_emit(monkeypatch, _emit_data(ratio="CBD puro"))
    actions = [a["action"] for a in audited]
    assert "prescription_regulatory_condition_missing" not in actions
    assert "prescription_regulatory_condition" not in actions
    assert "warning" not in result["reg_3"]
