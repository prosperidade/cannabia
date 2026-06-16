"""REG-8 — relatório de prontidão regulatória por tenant (RDCs 2026).

Consome o calendário (vigência 04/08/2026) + o estado de REG-1..4. Prontidão,
nunca aprovação; o médico é o decisor (B6).
"""
from __future__ import annotations

from datetime import date

from src.services.regulatory_readiness import check_regulatory_readiness


def _by_code(report, code):
    return next(f for f in report.findings if f.code == code)


def test_pre_vigencia(monkeypatch):
    monkeypatch.setenv("FF_RDC_2026_FORCE", "0")
    r = check_regulatory_readiness(42)
    assert r.rdc_2026_in_effect is False
    assert _by_code(r, "rdc_2026_vigencia").status == "pending"
    assert _by_code(r, "via_inalatoria").status == "blocked"
    assert _by_code(r, "thc_acima_0_2").status == "blocked"
    assert _by_code(r, "via_topica_dermatologica").status == "available"
    assert _by_code(r, "prescritor_tcle").status == "available"


def test_pos_vigencia(monkeypatch):
    monkeypatch.setenv("FF_RDC_2026_FORCE", "1")
    r = check_regulatory_readiness(42)
    assert r.rdc_2026_in_effect is True
    assert _by_code(r, "rdc_2026_vigencia").status == "available"
    assert _by_code(r, "via_inalatoria").status == "conditioned"
    assert _by_code(r, "thc_acima_0_2").status == "conditioned"


def test_today_param_decide_vigencia():
    assert check_regulatory_readiness(1, today=date(2026, 8, 3)).rdc_2026_in_effect is False
    assert check_regulatory_readiness(1, today=date(2026, 8, 4)).rdc_2026_in_effect is True


def test_to_dict_shape():
    d = check_regulatory_readiness(7, today=date(2026, 1, 1)).to_dict()
    assert d["tenant_id"] == 7
    assert d["vigencia_date"] == "2026-08-04"
    assert isinstance(d["findings"], list) and len(d["findings"]) == 5
    assert all({"code", "status", "message", "details"} <= set(f) for f in d["findings"])
