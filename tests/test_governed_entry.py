"""IA-2 — entrada governada única nos canais do paciente (29.4 R1 / C1).

WhatsApp e Triagem passam a executar o pipeline pelo MESMO caminho governado
(guardrails + billing + auditoria) do /ai/test, via run_governed_flow.
O modelo síncrono NÃO muda (cutover assíncrono é Onda 2).
"""
from __future__ import annotations

import pytest

import src.ai.service as svc
from src.ai.service import run_governed_flow
from src.ai.schemas import AnamnesisInput
from src.services.billing_service import BillingLimitExceeded


class _Allow:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.message = "quota"
        self.requests_used = 1
        self.requests_limit = 10


class _Guard:
    def __init__(self, passed=True):
        self.passed = passed
        self.reason = "motivo"
        self.blocked_by = type("B", (), {"value": "regex"})()


class _FakeFlow:
    def __init__(self, result):
        self._r = result

    def run(self, anamnesis):
        return self._r


def _anamnesis() -> AnamnesisInput:
    return AnamnesisInput(
        patient_name="P", age=40, main_complaint="dor", symptoms=["dor"],
        current_medications=[], allergies=[], medical_history="x",
    )


def _patch_gov(monkeypatch, allowed=True, guard_passed=True):
    audits: list = []
    monkeypatch.setattr(svc, "get_or_create_patient_by_name", lambda c, n: 1)
    monkeypatch.setattr(svc, "check_ai_allowance", lambda c: _Allow(allowed))
    monkeypatch.setattr(svc, "validate_input", lambda d: _Guard(guard_passed))
    monkeypatch.setattr(svc, "record_ai_usage", lambda **k: None)
    monkeypatch.setattr(svc, "save_ai_audit_log", lambda **k: audits.append(k))
    return audits


def test_guardrails_bloqueiam_e_auditam_security(monkeypatch):
    audits = _patch_gov(monkeypatch, guard_passed=False)
    with pytest.raises(ValueError):
        run_governed_flow(
            {"patient_name": "P"}, clinic_id=1, endpoint="whatsapp_anamnesis",
            anamnesis=_anamnesis(), flow=_FakeFlow({}),
        )
    assert audits and audits[-1]["status"] == "security_blocked"
    assert audits[-1]["endpoint"] == "whatsapp_anamnesis"


def test_billing_bloqueia_e_audita(monkeypatch):
    audits = _patch_gov(monkeypatch, allowed=False)
    with pytest.raises(BillingLimitExceeded):
        run_governed_flow(
            {"patient_name": "P"}, clinic_id=1, endpoint="triage_intake",
            anamnesis=_anamnesis(), flow=_FakeFlow({}),
        )
    assert audits[-1]["status"] == "billing_blocked"
    assert audits[-1]["endpoint"] == "triage_intake"


def test_sucesso_registra_uso_e_audita(monkeypatch):
    audits = _patch_gov(monkeypatch)
    used: list = []
    monkeypatch.setattr(svc, "record_ai_usage", lambda **k: used.append(k))
    monkeypatch.setattr(
        svc, "apply_to_output_dict",
        lambda r: (dict(r), type("G", (), {"passed": True, "reason": None})()),
    )
    result = {
        "clinical_analysis": {"risk_level": "baixo"},
        "token_usage": {"input": 10, "output": 5, "total": 15},
        "report_model": "gemini-2.5-flash",
    }
    out = run_governed_flow(
        {"patient_name": "P"}, clinic_id=1, endpoint="whatsapp_anamnesis",
        anamnesis=_anamnesis(), flow=_FakeFlow(result),
    )
    assert out["clinical_analysis"]["risk_level"] == "baixo"
    assert out["_guardrail_output"]["passed"] is True
    assert used and used[0]["clinic_id"] == 1
    assert audits[-1]["status"] == "success"
    assert audits[-1]["endpoint"] == "whatsapp_anamnesis"


def test_anamnese_whatsapp_passa_pelo_caminho_governado(monkeypatch):
    import src.ai.service as service_mod
    import src.services.anamnesis_flow as af

    called: dict = {}

    def fake_governed(data, *, clinic_id, endpoint, anamnesis=None, patient_name=None, **k):
        called.update(endpoint=endpoint, clinic_id=clinic_id)
        return {"clinical_analysis": {"risk_level": "baixo"}, "report_model": "gemini-2.5-flash", "rag_chunks_used": 0}

    monkeypatch.setattr(service_mod, "run_governed_flow", fake_governed)
    monkeypatch.setattr(af, "get_or_create_patient_by_name", lambda c, n: 1)
    monkeypatch.setattr(af, "update_patient_contact_if_missing", lambda *a, **k: None)
    monkeypatch.setattr(af, "save_report", lambda *a, **k: 7)
    monkeypatch.setattr(af, "create_event", lambda **k: None)
    monkeypatch.setattr(af, "_notify_doctor", lambda *a, **k: None)
    monkeypatch.setattr(af, "upsert_session", lambda *a, **k: None)
    monkeypatch.setattr(af, "send_whatsapp_text", lambda *a, **k: {})
    monkeypatch.setattr(af, "get_session", lambda c, p: {
        "step": "awaiting_history",
        "data": {"patient_name": "P", "age": 40, "main_complaint": "dor",
                 "symptoms": ["dor"], "current_medications": ["nenhuma"], "allergies": ["nenhuma"]},
    })

    af.process_message(1, "5511", "P", "sem historico")
    assert called.get("endpoint") == "whatsapp_anamnesis"
    assert called.get("clinic_id") == 1


def test_triagem_passa_pelo_caminho_governado(monkeypatch):
    import src.ai.service as service_mod
    import src.services.triage_intake_service as tis

    called: dict = {}
    monkeypatch.setattr(tis, "build_triage_payload", lambda payload: (_anamnesis(), {"patient_name": "P"}))
    monkeypatch.setattr(
        service_mod, "run_governed_flow",
        lambda data, *, clinic_id, endpoint, anamnesis=None, patient_name=None, **k: (
            called.update(endpoint=endpoint) or {"clinical_analysis": {}, "report_model": "x"}
        ),
    )
    monkeypatch.setattr(tis, "get_or_create_patient_by_name", lambda c, n: 1)
    monkeypatch.setattr(tis, "save_report", lambda *a, **k: 7)
    monkeypatch.setattr(tis, "create_event", lambda **k: None)
    monkeypatch.setattr(tis, "build_prescription_contract", lambda **k: {"ready": True})

    result = tis.submit_triage_intake({}, clinic_id=1)
    assert called.get("endpoint") == "triage_intake"
    assert result["report_id"] == 7
