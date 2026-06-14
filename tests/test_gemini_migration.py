"""IA-1 — migração Gemini 1.5 → 2.5 Flash + pricing + flag cost_unknown
(29.4 #2/#3, R2/R3/M1)."""
from __future__ import annotations

import logging

import src.ai.pricing as pricing
from src.ai.pricing import MODEL_PRICING, calculate_cost, has_pricing


def test_gemini_25_flash_no_pricing_e_custo_nao_zero():
    assert "gemini-2.5-flash" in MODEL_PRICING
    assert calculate_cost("gemini-2.5-flash", 1000, 1000) > 0


def test_gemini_15_flash_preservado_para_custo_historico():
    # Não removemos o 1.5: execuções já auditadas mantêm custo correto.
    assert "gemini-1.5-flash" in MODEL_PRICING


def test_has_pricing_flag():
    assert has_pricing("gemini-2.5-flash") is True
    assert has_pricing("gpt-4o-mini") is True
    assert has_pricing("modelo-inexistente") is False


def test_modelo_desconhecido_retorna_zero_e_loga_warning(caplog):
    pricing._warned_unknown_models.discard("modelo-xyz")
    with caplog.at_level(logging.WARNING, logger="cannabia.pricing"):
        cost = calculate_cost("modelo-xyz", 1000, 1000)
    assert cost == 0.0
    assert any(
        "cost_unknown" in r.message or "sem tarifa" in r.message for r in caplog.records
    )


def test_gemini_model_default_migrado_para_25():
    import src.ai.chains as chains
    assert chains.GEMINI_MODEL == "gemini-2.5-flash"
