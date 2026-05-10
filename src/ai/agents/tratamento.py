# src/ai/agents/tratamento.py
"""Agente de Tratamento — gera o plano terapêutico inicial a partir da análise clínica."""

from __future__ import annotations

from src.ai.agents.base import BaseAgent, AgentResult


class AgenteTratamento(BaseAgent):
    agent_name = "tratamento"
    description = "Gera plano terapêutico inicial a partir da análise clínica"

    def _register_skills(self):
        self.register_skill(
            "generate_treatment_plan",
            self._generate_treatment_plan,
            "Gera plano terapêutico estruturado para o caso clínico",
        )

    def _generate_treatment_plan(self, clinical_analysis: dict, **kwargs) -> dict:
        from src.ai.chains import run_treatment_plan
        from src.ai.schemas import ClinicalAnalysis

        analysis = ClinicalAnalysis(**clinical_analysis) if isinstance(clinical_analysis, dict) else clinical_analysis
        plan, tokens = run_treatment_plan(analysis)
        return {
            "treatment_plan": plan.model_dump() if hasattr(plan, "model_dump") else plan,
            "tokens": tokens,
        }

    def execute(self, **kwargs) -> AgentResult:
        clinical_analysis = kwargs.get("clinical_analysis")
        if not clinical_analysis:
            return AgentResult(success=False, error="clinical_analysis is required")

        result = self.invoke_skill("generate_treatment_plan", clinical_analysis=clinical_analysis)
        plan = result["treatment_plan"]
        tokens = result.get("tokens", {})

        return AgentResult(
            success=True,
            data={
                "treatment_plan": plan,
            },
            tokens=tokens if isinstance(tokens, dict) else {},
            confidence=0.78,
            skills_used=["generate_treatment_plan"],
        )
