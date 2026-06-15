"""REG-1 — via inalatória condicionada à vigência das RDCs de 2026.

Antes de 04/08/2026: mantém o aviso atual ("não regulamentada"). A partir da
vigência: regulamentada, condicionada a condição grave/debilitante/paliativa
registrada (REG-3). Sempre WARNING auditado — NUNCA bloqueia emissão (B6).
"""
from __future__ import annotations

from datetime import date

from src.ai.agents.regulatorio import check_anvisa
from src.services.regulatory_calendar import RDC_2026_VIGENCIA, is_rdc_2026_in_effect


# ── helper de vigência ─────────────────────────────────────────────────────

def test_helper_antes_da_vigencia_false():
    assert is_rdc_2026_in_effect(today=date(2026, 8, 3)) is False


def test_helper_na_vigencia_true():
    assert is_rdc_2026_in_effect(today=RDC_2026_VIGENCIA) is True
    assert is_rdc_2026_in_effect(today=date(2026, 8, 5)) is True


def test_helper_override_env_vence_a_data(monkeypatch):
    monkeypatch.setenv("FF_RDC_2026_FORCE", "1")
    assert is_rdc_2026_in_effect(today=date(2020, 1, 1)) is True
    monkeypatch.setenv("FF_RDC_2026_FORCE", "0")
    assert is_rdc_2026_in_effect(today=date(2030, 1, 1)) is False


# ── check_anvisa: via inalatória condicionada ──────────────────────────────

def _presc(route="inalatorio", condition="nenhuma", ratio="20:1", thc=20):
    return {
        "cannabinoid_ratio": ratio,
        "administration_route": route,
        "max_daily_mg": thc,
        "regulatory_condition": condition,
    }


def test_inalatoria_antes_vigencia_nao_regulamentada(monkeypatch):
    monkeypatch.setenv("FF_RDC_2026_FORCE", "0")
    out = check_anvisa(_presc())
    assert out["compliant"] is False
    assert any("regulamentada" in i.lower() for i in out["issues"])
    assert "RDC 327/2019" in out["checked_norms"]


def test_inalatoria_pos_vigencia_sem_condicao_exige_condicao(monkeypatch):
    monkeypatch.setenv("FF_RDC_2026_FORCE", "1")
    out = check_anvisa(_presc(condition="nenhuma"))
    assert out["compliant"] is False
    assert any("exige condicao" in i.lower() for i in out["issues"])
    assert "RDC 1.015/2026" in out["checked_norms"]


def test_inalatoria_pos_vigencia_com_condicao_grave_permitida(monkeypatch):
    monkeypatch.setenv("FF_RDC_2026_FORCE", "1")
    out = check_anvisa(_presc(condition="grave_debilitante"))
    assert all("inalat" not in i.lower() for i in out["issues"])
    assert out["compliant"] is True


def test_inalatoria_pos_vigencia_paliativa_permitida(monkeypatch):
    monkeypatch.setenv("FF_RDC_2026_FORCE", "1")
    out = check_anvisa(_presc(condition="paliativa"))
    assert all("inalat" not in i.lower() for i in out["issues"])


def test_via_sublingual_nao_afetada_pela_flag(monkeypatch):
    # via não-inalatória: flag não muda o comportamento da via
    monkeypatch.setenv("FF_RDC_2026_FORCE", "1")
    out = check_anvisa(_presc(route="sublingual"))
    assert out["compliant"] is True
