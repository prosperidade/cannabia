"""CLI-2 — Safety Clamp de THC (29.2 R2 / C3).

max_thc_daily_mg deixa de ser decorativo: o THC é derivado do ratio e cortado,
espelhando o clamp de CBD. Crítico para ratios ricos em THC (ex.: '1:3').
"""
from __future__ import annotations

from src.ai.prescriber import _clamp_recommendation, _thc_fraction_from_ratio, SafetyLimits
from src.ai.schemas import (
    AdministrationRoute,
    DosageRecommendation,
    ProductSpectrum,
    TitrationPhase,
    TitrationStep,
)


def _limits(max_cbd: float = 1000.0, max_thc: float = 10.0) -> SafetyLimits:
    return SafetyLimits(
        max_cbd_daily_mg=max_cbd,
        max_thc_daily_mg=max_thc,
        initial_cbd_mg_kg_day=0.5,
        recommended_spectrum=ProductSpectrum.FULL_SPECTRUM,
        recommended_ratio="1:3",
        recommended_route=AdministrationRoute.SUBLINGUAL,
        recommended_concentration=20.0,
        age_adjustment="adulto",
        drug_interactions=[],
        contraindications=[],
        warnings=[],
    )


def _rec(ratio: str, total_mg: float, max_daily: float = 200.0) -> DosageRecommendation:
    return DosageRecommendation(
        cannabinoid_ratio=ratio,
        spectrum=ProductSpectrum.FULL_SPECTRUM,
        administration_route=AdministrationRoute.SUBLINGUAL,
        concentration_mg_ml=20.0,
        titration_protocol=[TitrationStep(
            phase=TitrationPhase.MANUTENCAO,
            day_range="Dias 1-7",
            drops_per_dose=10,
            doses_per_day=2,
            concentration_mg_ml=20.0,
            total_daily_mg=total_mg,
        )],
        max_daily_mg=max_daily,
        clinical_rationale="teste",
        monitoring_checkpoints=["7 dias"],
        confidence_score=0.8,
        evidence_sources=[],
    )


def test_thc_fraction_from_ratio():
    assert abs(_thc_fraction_from_ratio("20:1") - 1 / 21) < 1e-6
    assert _thc_fraction_from_ratio("1:1") == 0.5
    assert _thc_fraction_from_ratio("1:3") == 0.75
    assert _thc_fraction_from_ratio("CBD puro") == 0.0
    assert _thc_fraction_from_ratio("isolado de CBD") == 0.0
    assert _thc_fraction_from_ratio("texto sem ratio") == 0.0
    assert _thc_fraction_from_ratio("") == 0.0


def test_clamp_corta_thc_em_ratio_rico():
    # ratio 1:3 -> THC = 75% do total. total=100 -> THC=75 > 10 mg/dia.
    out = _clamp_recommendation(_rec("1:3", total_mg=100.0), _limits(max_cbd=1000, max_thc=10))
    step = out.titration_protocol[0]
    # Total cortado para que THC <= 10 (10 / 0.75 ≈ 13.33)
    assert step.total_daily_mg <= 13.4
    assert step.total_daily_mg * 0.75 <= 10.0 + 0.05
    assert out.max_daily_mg <= 13.4


def test_clamp_nao_afeta_cbd_puro():
    out = _clamp_recommendation(_rec("CBD puro", total_mg=100.0), _limits(max_cbd=1000, max_thc=10))
    assert out.titration_protocol[0].total_daily_mg == 100.0


def test_clamp_cbd_continua_cortando():
    out = _clamp_recommendation(_rec("CBD puro", total_mg=2000.0), _limits(max_cbd=1000, max_thc=10))
    assert out.titration_protocol[0].total_daily_mg == 1000.0


def test_clamp_aplica_o_limite_mais_restritivo():
    # ratio 1:1 (THC 50%), max_thc=10 -> total limitado a 20; max_cbd=1000 não bind.
    out = _clamp_recommendation(_rec("1:1", total_mg=80.0), _limits(max_cbd=1000, max_thc=10))
    step = out.titration_protocol[0]
    assert step.total_daily_mg <= 20.05
    assert out.max_daily_mg <= 20.05
