from __future__ import annotations

import pytest

from src.services.prescription_contract import (
    PrescriptionContractError,
    build_dosage_input_or_raise,
    build_prescription_contract,
)


def _sample_report() -> dict:
    return {
        "id": 42,
        "patient_id": 7,
        "patient_name": "Maria Silva",
        "anamnesis_data": {
            "age": 48,
            "main_complaint": "Dor cronica",
            "symptoms": ["dor", "insonia"],
            "current_medications": ["duloxetina"],
            "allergies": ["penicilina"],
            "medical_history": "Fibromialgia ha 8 anos",
            "vital_signs": {
                "weight_kg": 63.5,
                "height_cm": 165,
            },
        },
        "clinical_analysis": {
            "probable_conditions": ["fibromialgia"],
            "risk_level": "moderado",
        },
    }


def test_build_prescription_contract_flags_missing_prior_cannabis_use():
    contract = build_prescription_contract(report=_sample_report())

    assert contract["ready"] is False
    assert contract["resolved_values"]["weight_kg"] == 63.5
    assert contract["resolved_values"]["height_cm"] == 165
    assert contract["source_map"]["weight_kg"] == "report.anamnesis_data.vital_signs.weight_kg"
    assert contract["missing_required_fields"] == [
        {"field": "prior_cannabis_use", "label": "Uso prévio de cannabis"}
    ]


def test_build_prescription_contract_merges_manual_overrides():
    contract = build_prescription_contract(
        report=_sample_report(),
        overrides={"prior_cannabis_use": "sim"},
    )

    assert contract["ready"] is True
    assert contract["resolved_values"]["prior_cannabis_use"] is True
    assert contract["source_map"]["prior_cannabis_use"] == "payload.prior_cannabis_use"
    assert contract["resolved_values"]["conditions"] == ["fibromialgia"]


def test_build_dosage_input_or_raise_returns_only_resolved_values():
    dosage_input = build_dosage_input_or_raise(
        report=_sample_report(),
        overrides={"prior_cannabis_use": False},
    )

    assert dosage_input["patient_name"] == "Maria Silva"
    assert dosage_input["weight_kg"] == 63.5
    assert dosage_input["prior_cannabis_use"] is False
    assert dosage_input["risk_level"] == "moderado"


def test_build_dosage_input_or_raise_raises_contract_error():
    with pytest.raises(PrescriptionContractError) as exc:
        build_dosage_input_or_raise(report=_sample_report())

    assert "Uso prévio de cannabis" in str(exc.value)
    assert exc.value.details["ready"] is False
