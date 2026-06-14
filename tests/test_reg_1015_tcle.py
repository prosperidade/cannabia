"""REG-1015 — prontidão RDC 1.015/2026 (já em vigor): TCLE vinculado à
prescrição + validação de prescritor habilitado. Não bloqueante; pendência de
revalidação contra o inteiro teor da RDC 1.015."""
from __future__ import annotations

from flask import Flask, g

import src.infra.audit as audit_mod
import src.services.prescription_service as psvc
from src.ai.agents.regulatorio import validate_prescriber_habilitation
from src.services.prescription_service import PrescriptionService


# ── validate_prescriber_habilitation ─────────────────────────────────────

def test_prescritor_com_crm_e_habilitado():
    out = validate_prescriber_habilitation("12345", 1)
    assert out["habilitado"] is True
    assert out["pending_revalidation"] is True
    assert out["norm_ref"] == "RDC 1.015/2026"


def test_prescritor_sem_crm_nao_habilitado():
    assert validate_prescriber_habilitation("", 1)["habilitado"] is False
    assert validate_prescriber_habilitation(None)["habilitado"] is False


# ── schema prescription_consents (migration 052) ──────────────────────────

def test_tabela_prescription_consents_aceita_registro(db_cursor):
    db_cursor.execute("SELECT id FROM clinics ORDER BY id LIMIT 1")
    row = db_cursor.fetchone()
    cid = row["id"] if row else 1
    db_cursor.execute(
        """
        INSERT INTO prescription_consents
            (clinic_id, prescription_id, patient_id, prescriber_crm,
             prescriber_habilitado, tcle_accepted)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, pending_revalidation, tcle_version, norm_ref
        """,
        (cid, 999, 5, "12345", True, None),
    )
    out = db_cursor.fetchone()
    assert out["id"] is not None
    assert out["pending_revalidation"] is True              # default
    assert out["tcle_version"] == "RDC-1.015/2026-min"      # default
    assert out["norm_ref"] == "RDC 1.015/2026"              # default


# ── emit_prescription: captura TCLE + audita prescritor não verificado ────

def _emit_data(crm: str = "12345") -> dict:
    return {
        "patient_id": 7,
        "doctor_user_id": 1,
        "doctor_name": "Dra. Maria",
        "doctor_crm": crm,
        "dosage_recommendation": {
            "cannabinoid_ratio": "20:1",
            "spectrum": "full_spectrum",
            "administration_route": "sublingual",
            "concentration_mg_ml": 50,
            "titration_protocol": [{
                "phase": "inicial", "day_range": "Dias 1-7", "drops_per_dose": 2,
                "doses_per_day": 2, "concentration_mg_ml": 50, "total_daily_mg": 10,
            }],
            "max_daily_mg": 40,
            "clinical_rationale": "Inicio baixo.",
            "contraindications": [],
            "drug_interactions": [],
            "monitoring_checkpoints": ["7 dias"],
            "confidence_score": 0.84,
            "evidence_sources": [],
        },
        "custom_notes": "n",
        "validity_days": 180,
    }


def test_emit_registra_tcle_e_audita_prescritor_nao_habilitado(monkeypatch):
    monkeypatch.setattr(psvc, "_save_prescription", lambda **k: 55)
    consents, audits = [], []
    monkeypatch.setattr(psvc, "_record_prescription_consent", lambda **k: consents.append(k) or 7)
    monkeypatch.setattr(audit_mod, "log_audit_event", lambda **k: audits.append(k))

    app = Flask(__name__)
    with app.test_request_context():
        g.clinic_id = 1
        result = PrescriptionService().emit_prescription(_emit_data(crm=""))

    assert result["prescription_id"] == 55                       # emitiu (não bloqueou)
    assert result["reg_1015"]["tcle_recorded"] is True
    assert result["reg_1015"]["prescriber_habilitado"] is False
    assert result["reg_1015"]["pending_revalidation"] is True
    assert consents and consents[0]["prescription_id"] == 55
    assert any(a["action"] == "prescription_prescriber_unverified" for a in audits)


def test_emit_prescritor_habilitado_nao_audita_unverified(monkeypatch):
    monkeypatch.setattr(psvc, "_save_prescription", lambda **k: 56)
    monkeypatch.setattr(psvc, "_record_prescription_consent", lambda **k: 8)
    audits = []
    monkeypatch.setattr(audit_mod, "log_audit_event", lambda **k: audits.append(k))

    app = Flask(__name__)
    with app.test_request_context():
        g.clinic_id = 1
        result = PrescriptionService().emit_prescription(_emit_data(crm="12345"))

    assert result["reg_1015"]["prescriber_habilitado"] is True
    assert not any(a["action"] == "prescription_prescriber_unverified" for a in audits)
