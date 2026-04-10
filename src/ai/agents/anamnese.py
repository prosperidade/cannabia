# src/ai/agents/anamnese.py
"""Agente de Anamnese — análise clínica estruturada dos sintomas do paciente."""

from __future__ import annotations
from src.ai.agents.base import BaseAgent, AgentResult


class AgenteAnamnese(BaseAgent):
    palace_room = "pipeline_anamnese"
    agent_name = "anamnese"
    description = "Analisa sintomas e gera avaliação clínica estruturada"

    def _register_skills(self):
        self.register_skill(
            "analyze_symptoms",
            self._analyze_symptoms,
            "Gera análise clínica a partir dos dados do paciente",
        )
        self.register_skill(
            "assess_risk_level",
            self._assess_risk,
            "Avalia nível de risco do paciente",
        )

    def _analyze_symptoms(self, **patient_data) -> dict:
        from src.ai.chains import run_clinical_analysis
        analysis, tokens = run_clinical_analysis(**patient_data)
        return {
            "clinical_analysis": analysis.model_dump() if hasattr(analysis, "model_dump") else analysis,
            "tokens": tokens,
        }

    def _assess_risk(self, clinical_analysis: dict, **kwargs) -> dict:
        risk = clinical_analysis.get("risk_level", "medio")
        red_flags = clinical_analysis.get("red_flags", [])
        return {
            "risk_level": risk,
            "red_flags": red_flags,
            "is_high_risk": risk in ("alto", "critico") or len(red_flags) > 0,
        }

    def execute(self, **kwargs) -> AgentResult:
        # Accept patient_data dict or individual fields
        patient_data = kwargs.get("patient_data", kwargs)

        # Recall similar cases from memory
        memory_ctx = kwargs.get("_memory_context")
        if memory_ctx and memory_ctx.get("has_memory"):
            patient_data["_similar_cases"] = memory_ctx.get("search_results", [])

        result = self.invoke_skill("analyze_symptoms", **patient_data)
        analysis = result["clinical_analysis"]
        tokens = result.get("tokens", {})

        risk = self.invoke_skill("assess_risk_level", clinical_analysis=analysis)

        return AgentResult(
            success=True,
            data={
                "clinical_analysis": analysis,
                "risk_level": risk["risk_level"],
                "is_high_risk": risk["is_high_risk"],
            },
            tokens=tokens if isinstance(tokens, dict) else {},
            confidence=0.8 if not risk["is_high_risk"] else 0.9,
            skills_used=["analyze_symptoms", "assess_risk_level"],
        )
