# src/ai/validators.py
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from pydantic import ValidationError

from src.ai.schemas import AnamnesisInput


# =========================
# Anti Prompt Injection
# =========================

_INJECTION_PATTERNS = [
    r"ignore (todas|todas as|previous|prior) instru(ç|c)(ões|oes)",
    r"return (the )?system prompt",
    r"show (the )?system prompt",
    r"reveal (the )?system prompt",
    r"system prompt",
    r"developer message",
    r"mensagem do desenvolvedor",
    r"policy",
    r"openai policy",
    r"tools?\b",
    r"function call",
    r"role\s*:\s*(system|developer|assistant|tool)",
    r"```",
    r"<\s*script\b",
    r"</\s*script\s*>",
    r"curl\s+http",
    r"wget\s+http",
]

_INJECTION_REGEX = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def _flatten_text_fields(payload: Dict[str, Any]) -> str:
    parts: List[str] = []
    for k, v in payload.items():
        if v is None:
            continue
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts.extend([str(x) for x in v if x is not None])
        else:
            parts.append(str(v))
    return " ".join(parts)


def validate_anamnesis_security(payload: Dict[str, Any]) -> None:
    """
    Levanta ValueError se detectar tentativa de prompt injection.
    """
    blob = _flatten_text_fields(payload)
    if _INJECTION_REGEX.search(blob):
        raise ValueError("Possível tentativa de prompt injection detectada.")


# =========================
# Normalização & limites
# =========================

_MAX_STR = 2000
_MAX_LIST_ITEMS = 40
_MAX_ITEM_STR = 200


def _clip_str(s: str, max_len: int) -> str:
    s = (s or "").strip()
    if len(s) > max_len:
        return s[:max_len]
    return s


def _norm_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        # Se vier string única, vira lista com 1 item
        value = [value]
    if not isinstance(value, list):
        value = [str(value)]

    out: List[str] = []
    for item in value[:_MAX_LIST_ITEMS]:
        if item is None:
            continue
        out.append(_clip_str(str(item), _MAX_ITEM_STR))
    return out


def normalize_anamnesis_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converte o payload em um formato consistente e seguro para o pipeline.
    Não confia em tipos vindo do client.
    """
    normalized: Dict[str, Any] = dict(payload or {})

    normalized["patient_name"] = _clip_str(str(normalized.get("patient_name", "")), 120)
    normalized["main_complaint"] = _clip_str(str(normalized.get("main_complaint", "")), _MAX_STR)
    normalized["medical_history"] = _clip_str(str(normalized.get("medical_history", "")), _MAX_STR)

    # int seguro
    try:
        normalized["age"] = int(normalized.get("age", 0))
    except Exception:
        normalized["age"] = 0

    normalized["symptoms"] = _norm_list(normalized.get("symptoms"))
    normalized["current_medications"] = _norm_list(normalized.get("current_medications"))
    normalized["allergies"] = _norm_list(normalized.get("allergies"))

    # remove campos que não fazem parte do schema (reduz superfície de ataque)
    allowed = {
        "patient_name",
        "age",
        "main_complaint",
        "symptoms",
        "current_medications",
        "allergies",
        "medical_history",
    }
    normalized = {k: v for k, v in normalized.items() if k in allowed}

    return normalized


def validate_anamnesis_payload(payload: Dict[str, Any]) -> AnamnesisInput:
    """
    Pipeline completo:
    1) anti-injection
    2) normaliza
    3) valida schema Pydantic
    """
    validate_anamnesis_security(payload)
    normalized = normalize_anamnesis_payload(payload)

    try:
        return AnamnesisInput(**normalized)
    except ValidationError as e:
        raise ValueError(f"Dados inválidos: {e}") from e
