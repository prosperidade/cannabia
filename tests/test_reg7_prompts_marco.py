"""REG-7 — prompts/templates citam o marco novo (RDCs 2026).

A RDC 327/2019 foi revogada pela 1.015/2026 (Art. 76). Prompts e citações
passam a referenciar o marco vigente; o override por DB (prompt_registry) segue
disponível para versões de runtime.
"""
from __future__ import annotations

from src.ai.agents.regulatorio import check_anvisa
from src.ai.prompts import PRESCRIBER_SYSTEM_PROMPT


def test_prompt_prescriber_cita_marco_2026():
    assert "1.015/2026" in PRESCRIBER_SYSTEM_PROMPT


def _thc_alto(route="oral"):
    return {"cannabinoid_ratio": "thc rico", "administration_route": route, "max_daily_mg": 50}


def test_thc_alto_cita_marco_condicional(monkeypatch):
    monkeypatch.setenv("FF_RDC_2026_FORCE", "0")  # pré-vigência
    out = check_anvisa(_thc_alto())
    assert any("327" in i for i in out["issues"])

    monkeypatch.setenv("FF_RDC_2026_FORCE", "1")  # pós-vigência
    out = check_anvisa(_thc_alto())
    assert any("1.015/2026" in i for i in out["issues"])
