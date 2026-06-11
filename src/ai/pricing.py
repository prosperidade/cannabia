# src/ai/pricing.py

MODEL_PRICING = {
    "gpt-4o-mini": {
        # OpenAI gpt-4o-mini: $0.15/1M input, $0.60/1M output (2024-)
        "input_per_1k": 0.00015,
        "output_per_1k": 0.00060,
    },
    "gemini-2.5-flash": {
        # Modelo ATIVO (substitui 1.5/2.0, descontinuados — 404). ai.google.dev/pricing:
        # $0.30/1M input (texto/imagem) + $2.50/1M output. Migracao jun/2026.
        "input_per_1k": 0.00030,
        "output_per_1k": 0.00250,
    },
    "gemini-1.5-flash": {
        # LEGACY — modelo descontinuado (404). Mantido em MODEL_PRICING apenas
        # para reanalise de custo de audit logs HISTORICOS gerados antes da
        # migracao (nao retornar 0.0). Nenhuma chamada produtiva usa mais.
        # Valores conhecidos da familia 1.5: $0.075/1M input + $0.30/1M output.
        "input_per_1k": 0.000075,
        "output_per_1k": 0.00030,
    },
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        return 0.0

    input_cost = (input_tokens or 0) / 1000 * pricing["input_per_1k"]
    output_cost = (output_tokens or 0) / 1000 * pricing["output_per_1k"]

    return round(input_cost + output_cost, 6)
