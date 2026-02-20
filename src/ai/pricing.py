# src/ai/pricing.py

MODEL_PRICING = {
    "gpt-4o-mini": {
        "input_per_1k": 0.00015,
        "output_per_1k": 0.00060,
    }
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        return 0.0

    input_cost = (input_tokens or 0) / 1000 * pricing["input_per_1k"]
    output_cost = (output_tokens or 0) / 1000 * pricing["output_per_1k"]

    return round(input_cost + output_cost, 6)
