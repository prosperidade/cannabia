# src/ai/agents/regulatorio.py
"""Agente Regulatorio — verifica compliance ANVISA/CFM usando Google Files
API + skill de elegibilidade ao Sandbox (F1.6 do docs/BACKLOG_SCC.md)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from src.ai.agents.base import AgentResult, BaseAgent

logger = logging.getLogger("cannabia.regulatorio_agent")


class AgenteRegulatorio(BaseAgent):
    palace_room = "regulatorio_anvisa"
    agent_name = "regulatorio"
    description = "Verifica compliance regulatoria ANVISA/CFM + elegibilidade Sandbox"

    def _register_skills(self):
        self.register_skill(
            "check_anvisa_compliance",
            self._check_anvisa,
            "Verifica se prescricao atende RDC 327/2019 e normas ANVISA",
        )
        self.register_skill(
            "query_legislation",
            self._query_legislation,
            "Consulta legislacao com contexto completo via Google Files API",
        )
        self.register_skill(
            "check_sandbox_eligibility",
            self._check_sandbox_eligibility,
            "Valida elegibilidade da associacao ao Sandbox Regulatorio (RDC 1.014/2026)",
        )

    # =====================================================================
    # Skills existentes
    # =====================================================================

    def _check_anvisa(self, prescription: dict, **kwargs) -> dict:
        ratio = prescription.get("cannabinoid_ratio", "")
        route = prescription.get("administration_route", "")
        thc_mg = prescription.get("max_daily_mg", 0)

        issues = []
        if "thc" in ratio.lower() and float(thc_mg or 0) > 40:
            issues.append("THC > 40mg/dia requer justificativa especial (RDC 327 Art. 8)")
        if route == "inalatorio":
            issues.append("Via inalatoria nao regulamentada pela ANVISA para cannabis medicinal")

        return {
            "compliant": len(issues) == 0,
            "issues": issues,
            "checked_norms": ["RDC 327/2019", "RDC 660/2022"],
        }

    def _query_legislation(self, question: str, **kwargs) -> dict:
        try:
            from src.knowledge.google_files import query_legislation_structured

            result, usage = query_legislation_structured(question, kwargs.get("file_names"))
            return {"result": result, "usage": usage, "source": "google_files_api"}
        except Exception as e:
            return {
                "result": {"answer": f"Erro ao consultar legislacao: {e}", "citations": []},
                "usage": {},
                "source": "error",
            }

    # =====================================================================
    # Skill nova: elegibilidade Sandbox (F1.6)
    # =====================================================================

    def _check_sandbox_eligibility(
        self,
        tenant_id: Optional[int] = None,
        association: Optional[dict] = None,
        **_kwargs,
    ) -> dict:
        """Executa a validacao formal de elegibilidade ao Sandbox e empacota
        o resultado num formato que o Orchestrador e o usuario final podem
        consumir: veredicto + blockers acionaveis + warnings.

        Aceita ``tenant_id`` direto ou um dict ``association`` contendo
        ``tenant_id`` — assinatura do BACKLOG permite qualquer uma.
        """
        resolved_tenant_id = tenant_id
        if resolved_tenant_id is None and association:
            resolved_tenant_id = association.get("tenant_id") or association.get("id")
        if resolved_tenant_id is None:
            return {
                "ok": False,
                "error": "tenant_id obrigatorio (ou association com tenant_id).",
            }

        try:
            from src.services.governance_service import check_sandbox_eligibility
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "error": f"Servico indisponivel: {exc}"}

        try:
            report = check_sandbox_eligibility(int(resolved_tenant_id))
        except ValueError as exc:
            return {"ok": False, "error": str(exc), "tenant_id": resolved_tenant_id}

        findings_summary = [
            {"code": f.code, "status": f.status, "message": f.message}
            for f in report.findings
        ]
        blockers = [
            {"code": f.code, "action": self._action_for(f.code, f.message)}
            for f in report.findings
            if f.status == "fail"
        ]
        warnings = [
            {"code": f.code, "message": f.message}
            for f in report.findings
            if f.status == "warn"
        ]

        # Audit trail no diary do palace_room (fire-and-forget via remember).
        self.remember(
            f"sandbox_eligibility tenant={resolved_tenant_id} "
            f"eligible={report.is_eligible} blockers={len(blockers)} warnings={len(warnings)}"
        )

        return {
            "ok": True,
            "tenant_id": int(resolved_tenant_id),
            "is_eligible": report.is_eligible,
            "has_warnings": report.has_warnings,
            "findings": findings_summary,
            "blockers": blockers,
            "warnings": warnings,
            "checked_norm": "RDC 1.014/2026",
        }

    @staticmethod
    def _action_for(code: str, fallback_message: str) -> str:
        """Traduz o code de um finding fail em uma acao operacional clara
        para a associacao. O fallback e a mensagem do proprio finding."""
        ACTIONS: dict[str, str] = {
            "legal_nature": (
                "Atualize o cadastro para tenant_type='association'. "
                "Clinicas e medicos independentes nao sao elegiveis."
            ),
            "incorporation_time": (
                "Preencha incorporation_date no cadastro institucional. "
                "A RDC exige pelo menos 2 anos de constituicao."
            ),
            "active_technical_responsible": (
                "Cadastre ao menos um Responsavel Tecnico ativo em "
                "/api/v1/governance/rts com habilitation_valid_until futura."
            ),
            "technical_operational_capacity": (
                "Registre uma avaliacao de capacidade em "
                "/api/v1/governance/capacity (scores de infraestrutura, "
                "RH, processos e escala proposta)."
            ),
        }
        return ACTIONS.get(code, fallback_message)

    # =====================================================================
    # Execute
    # =====================================================================

    def execute(self, **kwargs: Any) -> AgentResult:
        prescription = kwargs.get("prescription", kwargs.get("recommendation", {}))
        question = kwargs.get("question")
        tenant_id = kwargs.get("tenant_id")
        association = kwargs.get("association")

        skills_used: list[str] = []

        if prescription:
            compliance = self.invoke_skill("check_anvisa_compliance", prescription=prescription)
            skills_used.append("check_anvisa_compliance")
            if not compliance["compliant"]:
                self.remember(f"Compliance issues: {compliance['issues']}")
        else:
            compliance = {"compliant": True, "issues": [], "checked_norms": []}

        legislation_result = None
        if question:
            legislation_result = self.invoke_skill("query_legislation", question=question)
            skills_used.append("query_legislation")

        eligibility_result = None
        if tenant_id is not None or association:
            eligibility_result = self.invoke_skill(
                "check_sandbox_eligibility",
                tenant_id=tenant_id,
                association=association,
            )
            skills_used.append("check_sandbox_eligibility")

        # Confidence composta: compliance sozinho calibra 0.9/0.6 como antes.
        # Se houve check de elegibilidade e ela falhou, rebaixa para 0.5.
        confidence = 0.9 if compliance["compliant"] else 0.6
        if eligibility_result and eligibility_result.get("ok") and not eligibility_result.get("is_eligible"):
            confidence = min(confidence, 0.5)

        return AgentResult(
            success=True,
            data={
                "compliance": compliance,
                "legislation": legislation_result,
                "sandbox_eligibility": eligibility_result,
            },
            confidence=confidence,
            skills_used=skills_used,
        )
