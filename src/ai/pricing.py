# src/ai/pricing.py

MODEL_PRICING = {
    "gpt-4o-mini": {
        # OpenAI gpt-4o-mini: $0.15/1M input, $0.60/1M output (2024-)
        "input_per_1k": 0.00015,
        "output_per_1k": 0.00060,
    },
    "gemini-1.5-flash": {
        # Legacy pricing — modelo nao esta mais em ai.google.dev/pricing.
        # Verificado 2026-05-09 contra valores conhecidos:
        # $0.075/1M input + $0.30/1M output (≤128k contexto).
        # ⚠️ Migrar para gemini-2.5-flash ou gemini-2.5-flash-lite antes de
        # jun/2026 (Google deprecated 1.5/2.0). Ver docs/BACKLOG_AI_MIGRATION.md
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
