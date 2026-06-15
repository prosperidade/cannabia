"""REG-6 — intake captura contexto regulatório (RDCs 2026).

Campos novos (via preferida, uso paliativo, condição grave) no nível do schema
(AnamnesisInput), populáveis por QUALQUER canal: triagem web, WhatsApp, app do
paciente. `regulatory_condition` derivado alimenta REG-3/REG-4.
"""
from __future__ import annotations

from src.ai.schemas import AnamnesisInput, RegulatoryCondition, derive_regulatory_condition
from src.services.anamnesis_flow import _normalize_route_preference
from src.services.triage_intake_service import build_triage_payload


def test_derive_regulatory_condition():
    assert derive_regulatory_condition(grave_condition=True) is RegulatoryCondition.GRAVE_DEBILITANTE
    assert derive_regulatory_condition(palliative_use=True) is RegulatoryCondition.PALIATIVA
    # paliativo tem precedência quando ambos
    assert derive_regulatory_condition(grave_condition=True, palliative_use=True) is RegulatoryCondition.PALIATIVA
    assert derive_regulatory_condition() is RegulatoryCondition.NENHUMA


def test_anamnesis_input_aceita_campos_reg6():
    ai = AnamnesisInput(
        patient_name="A", age=40, main_complaint="dor", symptoms=["dor"],
        preferred_route="topico", palliative_use=True, grave_condition=False,
        regulatory_condition="paliativa",
    )
    assert ai.preferred_route == "topico"
    assert ai.regulatory_condition == "paliativa"


def test_whatsapp_route_normalizer_linguagem_leiga():
    assert _normalize_route_preference("1") == "sublingual"
    assert _normalize_route_preference("quero pomada") == "topico"
    assert _normalize_route_preference("4") == "inalatorio"
    assert _normalize_route_preference("cápsula") == "oral"
    assert _normalize_route_preference("sei la") is None


def test_triagem_deriva_regulatory_condition():
    payload = {
        "identificacao": {"patient_name": "Ana", "age": 40},
        "motivo": {"objetivo_principal": "dor cronica"},
        "dados_fisicos": {"peso_kg": 70, "altura_cm": 165},
        "sintomas": ["dor"],
        "habitos": {},
        "contexto_clinico": {"uso_paliativo": True, "via_preferida": "topico"},
    }
    ai, data = build_triage_payload(payload)
    assert ai.regulatory_condition == "paliativa"
    assert data["regulatory_condition"] == "paliativa"
    assert ai.preferred_route == "topico"
