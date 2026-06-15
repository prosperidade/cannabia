"""REG-2 — protocolos por via (tópica/inalatória) + unidade por via.

Protocolos de referência conservadores p/ TOPICO/INALATORIO (ajustáveis pelo
médico — B6) e parametrização de unidade de dose por via (não só gotas).
"""
from __future__ import annotations

from src.ai.prescriber import (
    CONDITION_PROTOCOLS,
    SafetyLimits,
    _clamp_recommendation,
    _match_condition,
    calculate_safety_limits,
    dose_unit_for_route,
)
from src.ai.schemas import (
    AdministrationRoute,
    DosageInput,
    DosageRecommendation,
    ProductSpectrum,
    TitrationPhase,
    TitrationStep,
)


# ── protocolos das novas vias ──────────────────────────────────────────────

def test_protocolos_novas_vias_existem():
    assert CONDITION_PROTOCOLS["dor localizada"]["route"] is AdministrationRoute.TOPICO
    assert CONDITION_PROTOCOLS["dor aguda"]["route"] is AdministrationRoute.INALATORIO


def test_match_condition_novas_vias():
    assert _match_condition(["dor localizada"], [], "") == "dor localizada"
    assert _match_condition([], [], "paciente com dor aguda") == "dor aguda"


def test_calculate_safety_limits_via_topica():
    di = DosageInput(
        patient_name="A", age=40, weight_kg=70.0, main_complaint="dor localizada",
        symptoms=["dor"], conditions=["dor localizada"],
    )
    assert calculate_safety_limits(di).recommended_route is AdministrationRoute.TOPICO


# ── unidade por via ────────────────────────────────────────────────────────

def test_dose_unit_for_route():
    assert dose_unit_for_route(AdministrationRoute.SUBLINGUAL) == "gota"
    assert dose_unit_for_route(AdministrationRoute.ORAL, plural=True) == "gotas"
    assert dose_unit_for_route(AdministrationRoute.TOPICO, plural=True) == "aplicações"
    assert dose_unit_for_route(AdministrationRoute.INALATORIO, plural=True) == "inalações"


# ── clamp ciente da via (não-conta-gotas escala a contagem) ────────────────

def test_clamp_via_topica_escala_contagem():
    rec = DosageRecommendation(
        cannabinoid_ratio="CBD puro", spectrum=ProductSpectrum.BROAD_SPECTRUM,
        administration_route=AdministrationRoute.TOPICO, concentration_mg_ml=50.0,
        titration_protocol=[TitrationStep(
            phase=TitrationPhase.INICIAL, day_range="Dias 1-7", drops_per_dose=10,
            doses_per_day=2, concentration_mg_ml=50.0, total_daily_mg=200.0,
        )],
        max_daily_mg=200.0, clinical_rationale="x", contraindications=[],
        drug_interactions=[], monitoring_checkpoints=["7d"], confidence_score=0.8,
        evidence_sources=[],
    )
    limits = SafetyLimits(
        max_cbd_daily_mg=100.0, max_thc_daily_mg=40.0, initial_cbd_mg_kg_day=1.0,
        recommended_spectrum=ProductSpectrum.BROAD_SPECTRUM, recommended_ratio="CBD puro",
        recommended_route=AdministrationRoute.TOPICO, recommended_concentration=50.0,
        age_adjustment="adulto", drug_interactions=[], contraindications=[], warnings=[],
    )
    out = _clamp_recommendation(rec, limits)
    # CBD cortado de 200 -> 100; contagem escala 10 * (100/200) = 5 (aplicações)
    assert out.titration_protocol[0].total_daily_mg == 100.0
    assert out.titration_protocol[0].drops_per_dose == 5
