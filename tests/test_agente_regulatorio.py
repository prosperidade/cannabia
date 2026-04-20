"""Testes do AgenteRegulatorio (F1.6 do SCC).

Cobre skills existentes + a skill nova check_sandbox_eligibility +
integracao via execute().
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.ai.agents.regulatorio import AgenteRegulatorio
from src.services.governance_service import EligibilityFinding, EligibilityReport


@pytest.fixture
def agent(monkeypatch):
    # Isola o diary fire-and-forget — testes nao dependem do MemPalace real.
    monkeypatch.setattr("src.ai.agents.base.diary_write", lambda *a, **kw: True)
    return AgenteRegulatorio()


def _report(findings: list[EligibilityFinding]) -> EligibilityReport:
    return EligibilityReport(
        tenant_id=42,
        checked_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
        findings=findings,
    )


# ---------------------------------------------------------------------
# Skill: check_sandbox_eligibility
# ---------------------------------------------------------------------

class TestSandboxEligibilitySkill:
    def test_skill_is_registered(self, agent):
        assert "check_sandbox_eligibility" in agent.get_skills()

    def test_returns_error_when_no_tenant_id_or_association(self, agent):
        out = agent.invoke_skill("check_sandbox_eligibility")
        assert out["ok"] is False
        assert "tenant_id obrigatorio" in out["error"]

    def test_accepts_tenant_id_direct(self, agent, monkeypatch):
        captured = {}

        def fake(tid, **_):
            captured["tid"] = tid
            return _report([
                EligibilityFinding(code="legal_nature", status="pass", message="ok"),
            ])

        monkeypatch.setattr(
            "src.services.governance_service.check_sandbox_eligibility", fake
        )
        out = agent.invoke_skill("check_sandbox_eligibility", tenant_id=42)
        assert out["ok"] is True
        assert captured["tid"] == 42
        assert out["tenant_id"] == 42
        assert out["is_eligible"] is True

    def test_accepts_association_dict_fallback(self, agent, monkeypatch):
        monkeypatch.setattr(
            "src.services.governance_service.check_sandbox_eligibility",
            lambda tid, **_: _report([
                EligibilityFinding(code="legal_nature", status="pass", message="ok"),
            ]),
        )
        out = agent.invoke_skill(
            "check_sandbox_eligibility",
            association={"tenant_id": 7, "name": "X"},
        )
        assert out["ok"] is True
        assert out["tenant_id"] == 7

    def test_surfaces_blockers_with_actionable_hints(self, agent, monkeypatch):
        monkeypatch.setattr(
            "src.services.governance_service.check_sandbox_eligibility",
            lambda tid, **_: _report([
                EligibilityFinding(code="legal_nature", status="pass", message="ok"),
                EligibilityFinding(
                    code="incorporation_time", status="fail",
                    message="Tempo minimo de 2 anos nao atingido.",
                ),
                EligibilityFinding(
                    code="active_technical_responsible", status="fail",
                    message="Nenhum RT ativo.",
                ),
                EligibilityFinding(
                    code="statute_document", status="warn",
                    message="Sem estatuto.",
                ),
            ]),
        )
        out = agent.invoke_skill("check_sandbox_eligibility", tenant_id=42)
        assert out["is_eligible"] is False
        assert out["has_warnings"] is True

        blocker_codes = {b["code"] for b in out["blockers"]}
        assert blocker_codes == {"incorporation_time", "active_technical_responsible"}

        # As actions mapeadas sao retornadas (nao a message crua do finding).
        inc_blocker = next(b for b in out["blockers"] if b["code"] == "incorporation_time")
        assert "incorporation_date" in inc_blocker["action"]

        rt_blocker = next(b for b in out["blockers"] if b["code"] == "active_technical_responsible")
        assert "/api/v1/governance/rts" in rt_blocker["action"]

        assert [w["code"] for w in out["warnings"]] == ["statute_document"]
        assert out["checked_norm"] == "RDC 1.014/2026"

    def test_unknown_finding_code_falls_back_to_message(self, agent, monkeypatch):
        monkeypatch.setattr(
            "src.services.governance_service.check_sandbox_eligibility",
            lambda tid, **_: _report([
                EligibilityFinding(
                    code="some_future_code", status="fail",
                    message="Mensagem crua do finding.",
                ),
            ]),
        )
        out = agent.invoke_skill("check_sandbox_eligibility", tenant_id=42)
        assert out["blockers"][0]["action"] == "Mensagem crua do finding."

    def test_tenant_not_found_returns_error(self, agent, monkeypatch):
        def raise_missing(tid, **_):
            raise ValueError("Tenant 42 nao encontrado.")

        monkeypatch.setattr(
            "src.services.governance_service.check_sandbox_eligibility", raise_missing
        )
        out = agent.invoke_skill("check_sandbox_eligibility", tenant_id=42)
        assert out["ok"] is False
        assert "nao encontrado" in out["error"]
        assert out["tenant_id"] == 42


# ---------------------------------------------------------------------
# Skill: check_anvisa_compliance (smoke de nao regressao)
# ---------------------------------------------------------------------

class TestAnvisaCompliance:
    def test_compliant_prescription_passes(self, agent):
        out = agent.invoke_skill(
            "check_anvisa_compliance",
            prescription={"cannabinoid_ratio": "cbd-rich", "administration_route": "oral", "max_daily_mg": 20},
        )
        assert out["compliant"] is True
        assert out["issues"] == []

    def test_thc_over_40mg_flagged(self, agent):
        out = agent.invoke_skill(
            "check_anvisa_compliance",
            prescription={"cannabinoid_ratio": "thc-dominant", "max_daily_mg": 60},
        )
        assert out["compliant"] is False
        assert any("RDC 327" in issue for issue in out["issues"])

    def test_inhalatory_route_flagged(self, agent):
        out = agent.invoke_skill(
            "check_anvisa_compliance",
            prescription={"administration_route": "inalatorio", "max_daily_mg": 10},
        )
        assert out["compliant"] is False


# ---------------------------------------------------------------------
# execute() — orquestracao
# ---------------------------------------------------------------------

class TestExecute:
    def test_execute_without_inputs_returns_success_defaults(self, agent):
        result = agent.execute()
        assert result.success is True
        assert result.data["compliance"]["compliant"] is True
        assert result.data["sandbox_eligibility"] is None
        assert result.skills_used == []

    def test_execute_runs_eligibility_when_tenant_id_provided(self, agent, monkeypatch):
        monkeypatch.setattr(
            "src.services.governance_service.check_sandbox_eligibility",
            lambda tid, **_: _report([
                EligibilityFinding(code="legal_nature", status="pass", message="ok"),
            ]),
        )
        result = agent.execute(tenant_id=42)
        assert "check_sandbox_eligibility" in result.skills_used
        assert result.data["sandbox_eligibility"]["is_eligible"] is True

    def test_execute_lowers_confidence_when_sandbox_not_eligible(self, agent, monkeypatch):
        monkeypatch.setattr(
            "src.services.governance_service.check_sandbox_eligibility",
            lambda tid, **_: _report([
                EligibilityFinding(code="legal_nature", status="fail", message="no"),
            ]),
        )
        result = agent.execute(tenant_id=42)
        # Sem prescricao compliance["compliant"] e True (confidence base 0.9),
        # mas elegibilidade falha → rebaixa para 0.5.
        assert result.confidence == 0.5

    def test_execute_keeps_low_confidence_when_compliance_fails(self, agent):
        result = agent.execute(prescription={"administration_route": "inalatorio"})
        assert result.confidence == 0.6  # compliance falha mas sem eligibility

    def test_execute_lowest_confidence_when_both_fail(self, agent, monkeypatch):
        monkeypatch.setattr(
            "src.services.governance_service.check_sandbox_eligibility",
            lambda tid, **_: _report([
                EligibilityFinding(code="legal_nature", status="fail", message="no"),
            ]),
        )
        result = agent.execute(
            tenant_id=42,
            prescription={"administration_route": "inalatorio"},
        )
        # min(0.6, 0.5) = 0.5
        assert result.confidence == 0.5
