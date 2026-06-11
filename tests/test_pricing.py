"""Testes de src/ai/pricing.py (Sprint 1 Track B.2).

Valida que:
  1. gpt-4o-mini retorna custo nao-zero (regressao).
  2. gemini-1.5-flash retorna custo nao-zero (correcao do bug de cost
     mixing — antes calculate_cost retornava 0.0 para Gemini).
  3. Modelo desconhecido retorna 0.0 (defensive default mantido).
  4. Tokens zero retornam 0.0 sem dividir por zero.
"""

from src.ai.pricing import MODEL_PRICING, calculate_cost


def test_gpt4o_mini_cost_known_baseline():
    # 1000 input + 1000 output tokens
    cost = calculate_cost("gpt-4o-mini", 1000, 1000)
    # 1k * 0.00015 + 1k * 0.00060 = 0.00015 + 0.00060 = 0.00075
    assert cost == 0.00075


def test_gemini_15_flash_cost_known_baseline():
    # 1000 input + 1000 output tokens
    cost = calculate_cost("gemini-1.5-flash", 1000, 1000)
    # 1k * 0.000075 + 1k * 0.00030 = 0.000075 + 0.00030 = 0.000375
    assert cost == 0.000375


def test_gemini_25_flash_cost_known_baseline():
    # Modelo ATIVO (substitui 1.5/2.0 descontinuados). 1000 input + 1000 output:
    # 1k * 0.00030 + 1k * 0.00250 = 0.00030 + 0.00250 = 0.00280
    cost = calculate_cost("gemini-2.5-flash", 1000, 1000)
    assert cost == 0.0028


def test_active_gemini_model_priced_no_silent_zero():
    # Regressao M1 (doc 30): o modelo Gemini ativo do pipeline NAO pode retornar
    # custo 0.0 silencioso por ausencia em MODEL_PRICING.
    assert "gemini-2.5-flash" in MODEL_PRICING
    assert calculate_cost("gemini-2.5-flash", 1000, 500) > 0


def test_gemini_15_flash_cheaper_than_gpt4o_mini():
    # Sanity: para o mesmo numero de tokens, Gemini 1.5 Flash deve ser mais
    # barato que gpt-4o-mini (input: $0.075/1M vs $0.15/1M; output: $0.30/1M
    # vs $0.60/1M — exatamente metade em ambos).
    gpt = calculate_cost("gpt-4o-mini", 5000, 2500)
    gem = calculate_cost("gemini-1.5-flash", 5000, 2500)
    assert gem == gpt / 2


def test_unknown_model_returns_zero():
    # Defensive default: nunca quebra o pipeline mesmo se modelo novo aparecer
    # no audit antes de pricing ser atualizado.
    assert calculate_cost("gpt-4o", 1000, 1000) == 0.0
    assert calculate_cost("claude-opus-4", 1000, 1000) == 0.0


def test_zero_tokens_returns_zero():
    assert calculate_cost("gpt-4o-mini", 0, 0) == 0.0
    assert calculate_cost("gemini-1.5-flash", 0, 0) == 0.0


def test_none_tokens_treated_as_zero():
    # service.py pode passar None quando o flow falha antes do LLM responder.
    assert calculate_cost("gpt-4o-mini", None, None) == 0.0


def test_pricing_table_includes_both_models():
    assert "gpt-4o-mini" in MODEL_PRICING
    assert "gemini-2.5-flash" in MODEL_PRICING  # ativo
    assert "gemini-1.5-flash" in MODEL_PRICING  # legacy (audit logs historicos)
    for model, rates in MODEL_PRICING.items():
        assert "input_per_1k" in rates, f"{model} sem input_per_1k"
        assert "output_per_1k" in rates, f"{model} sem output_per_1k"
        assert rates["input_per_1k"] > 0
        assert rates["output_per_1k"] > 0
