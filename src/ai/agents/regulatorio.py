# src/ai/agents/regulatorio.py
"""Agente Regulatório — verifica compliance ANVISA/CFM usando Google Files API."""

from __future__ import annotations
from src.ai.agents.base import BaseAgent, AgentResult


class AgenteRegulatorio(BaseAgent):
    palace_room = "regulatorio_anvisa"
    agent_name = "regulatorio"
    description = "Verifica compliance regulatória ANVISA/CFM via Google Files API"

    def _register_skills(self):
        self.register_skill(
            "check_anvisa_compliance",
            self._check_anvisa,
            "Verifica se prescrição atende RDC 327/2019 e normas ANVISA",
        )
        self.register_skill(
            "query_legislation",
            self._query_legislation,
            "Consulta legislação com contexto completo via Google Files API",
        )

    def _check_anvisa(self, prescription: dict, **kwargs) -> dict:
        ratio = prescription.get("cannabinoid_ratio", "")
        route = prescription.get("administration_route", "")
        thc_mg = prescription.get("max_daily_mg", 0)

        issues = []
        # Basic ANVISA RDC 327 checks
        if "thc" in ratio.lower() and float(thc_mg or 0) > 40:
            issues.append("THC > 40mg/dia requer justificativa especial (RDC 327 Art. 8)")
        if route == "inalatorio":
            issues.append("Via inalatória não regulamentada pela ANVISA para cannabis medicinal")

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
            return {"result": {"answer": f"Erro ao consultar legislação: {e}", "citations": []},
                    "usage": {}, "source": "error"}

    def execute(self, **kwargs) -> AgentResult:
        prescription = kwargs.get("prescription", kwargs.get("recommendation", {}))
        question = kwargs.get("question")

        skills_used = []

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

        return AgentResult(
            success=True,
            data={
                "compliance": compliance,
                "legislation": legislation_result,
            },
            confidence=0.9 if compliance["compliant"] else 0.6,
            skills_used=skills_used,
        )
