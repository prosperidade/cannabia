"""REG-4 — THC > 0,2% condicionado à condição grave/paliativa (RDCs 2026).

Teor do produto > 0,2% só indicado para doença grave/debilitante ou que ameace
a vida (paliativa); contraindicado a <18, gestantes e lactantes. Com a condição
registrada (e paciente não vulnerável), o Safety Clamp de THC vira AVISO — o
médico é o decisor (B6). Sem condição: corta como na Onda 1 (B5).
"""
from __future__ import annotations

from src.ai.prescriber import (
    SafetyLimits,
    _clamp_recommendation,
    calculate_safety_limits,
    is_high_thc_product,
)
from src.ai.schemas import (
    AdministrationRoute,
    DosageInput,
    DosageRecommendation,
    ProductSpectrum,
    TitrationPhase,
    TitrationStep,
)


# ── teor de THC do produto (limiar 0,2% ≈ 2 mg/mL) ─────────────────────────

def test_is_high_thc_product():
    assert is_high_thc_product("1:1", 50) is True      # 25 mg/mL
    assert is_high_thc_product("20:1", 20) is False     # ~0,95 mg/mL
    assert is_high_thc_product("CBD puro", 100) is False
    assert is_high_thc_product("1:1", 2) is False        # 1 mg/mL < 2


# ── calculate_safety_limits: modo do clamp por condição/vulnerabilidade ────

def _di(condition="nenhuma", age=40, conditions=None):
    return DosageInput(
        patient_name="A", age=age, weight_kg=70.0, main_complaint="dor",
        symptoms=["dor"], conditions=conditions or [], regulatory_condition=condition,
    )


def test_grave_adulto_clamp_soft():
    assert calculate_safety_limits(_di(condition="grave_debilitante")).thc_clamp_soft is True
    assert calculate_safety_limits(_di(condition="paliativa")).thc_clamp_soft is True


def test_nenhuma_clamp_hard():
    assert calculate_safety_limits(_di(condition="nenhuma")).thc_clamp_soft is False


def test_grave_menor_de_idade_nao_soft_e_avisa():
    lim = calculate_safety_limits(_di(condition="paliativa", age=15))
    assert lim.thc_clamp_soft is False
    assert any("se aplica" in w.lower() for w in lim.warnings)


def test_grave_gestante_nao_soft():
    lim = calculate_safety_limits(_di(condition="grave_debilitante", conditions=["gestante"]))
    assert lim.thc_clamp_soft is False


# ── _clamp_recommendation: corta (hard) vs avisa (soft) ────────────────────

def _limits(thc_clamp_soft=False):
    return SafetyLimits(
        max_cbd_daily_mg=1000.0, max_thc_daily_mg=40.0, initial_cbd_mg_kg_day=1.0,
        recommended_spectrum=ProductSpectrum.FULL_SPECTRUM, recommended_ratio="1:1",
        recommended_route=AdministrationRoute.SUBLINGUAL, recommended_concentration=50.0,
        age_adjustment="adulto", drug_interactions=[], contraindications=[], warnings=[],
        thc_clamp_soft=thc_clamp_soft,
    )


def _rec(total=100.0, ratio="1:1", conc=50.0):
    return DosageRecommendation(
        cannabinoid_ratio=ratio, spectrum=ProductSpectrum.FULL_SPECTRUM,
        administration_route=AdministrationRoute.SUBLINGUAL, concentration_mg_ml=conc,
        titration_protocol=[TitrationStep(
            phase=TitrationPhase.INICIAL, day_range="Dias 1-7", drops_per_dose=10,
            doses_per_day=2, concentration_mg_ml=conc, total_daily_mg=total,
        )],
        max_daily_mg=total, clinical_rationale="x", contraindications=[],
        drug_interactions=[], monitoring_checkpoints=["7 dias"], confidence_score=0.8,
        evidence_sources=[],
    )


def test_clamp_hard_corta_thc_sem_condicao():
    # THC = 100 * 0.5 = 50 > 40 -> corta total para 80 (40/0.5)
    out = _clamp_recommendation(_rec(total=100.0), _limits(thc_clamp_soft=False))
    assert out.titration_protocol[0].total_daily_mg <= 80.1
    assert out.max_daily_mg <= 80.1


def test_clamp_soft_nao_corta_com_condicao_grave():
    out = _clamp_recommendation(_rec(total=100.0), _limits(thc_clamp_soft=True))
    assert out.titration_protocol[0].total_daily_mg == 100.0   # mantido (aviso, não corte)
    assert out.max_daily_mg == 100.0
