# src/ai/agents/triagem.py
"""Agente de Triagem — extrai condições clínicas do relato do paciente via widgets."""

from __future__ import annotations
from src.ai.agents.base import BaseAgent, AgentResult


class AgenteTriagem(BaseAgent):
    agent_name = "triagem"
    description = "Extrai condições clínicas do relato do paciente usando widgets interativos"

    def _register_skills(self):
        self.register_skill(
            "extract_conditions",
            self._extract_conditions,
            "Extrai condições clínicas do texto do paciente",
        )
        self.register_skill(
            "detect_red_flags",
            self._detect_red_flags,
            "Detecta sinais de alerta (dor torácica, ideação suicida, etc)",
        )

    def _extract_conditions(self, patient_message: str, **kwargs) -> dict:
        from src.ai.chains import run_triage_agent
        response, tokens = run_triage_agent(
            patient_message=patient_message,
            patient_name=kwargs.get("patient_name", ""),
            age=kwargs.get("age"),
            clinic_id=kwargs.get("clinic_id", ""),
            prior_context=kwargs.get("prior_context", ""),
            provider=kwargs.get("provider", "openai"),
        )
        return {
            "triage_response": response.model_dump() if hasattr(response, "model_dump") else response,
            "tokens": tokens,
        }

    def _detect_red_flags(self, triage_response: dict, **kwargs) -> dict:
        conditions = triage_response.get("extracted_conditions", [])
        red_flags = []
        high_urgency_keywords = ["suicid", "toraci", "infart", "convuls", "anafilax"]
        for cond in conditions:
            name = (cond.get("condition_name") or "").lower()
            if any(kw in name for kw in high_urgency_keywords):
                red_flags.append(cond)
        return {"red_flags": red_flags, "has_red_flags": bool(red_flags)}

    def execute(self, **kwargs) -> AgentResult:
        patient_message = kwargs.get("patient_message", "")
        if not patient_message:
            return AgentResult(success=False, error="patient_message is required")

        result = self.invoke_skill("extract_conditions", **kwargs)
        triage = result["triage_response"]
        tokens = result.get("tokens", {})

        # Check red flags
        flags = self.invoke_skill("detect_red_flags", triage_response=triage)

        # Knowledge graph fire-and-forget via MemPalace foi extirpado em
        # Track C.2 — condicoes detectadas vivem apenas no AgentResult
        # retornado, consumidores podem persistir explicitamente se precisarem.
        conditions = triage.get("extracted_conditions", [])

        return AgentResult(
            success=True,
            data={
                "triage_response": triage,
                "red_flags": flags["red_flags"],
                "has_red_flags": flags["has_red_flags"],
                "conditions_count": len(conditions),
            },
            tokens=tokens if isinstance(tokens, dict) else {},
            confidence=0.85 if not flags["has_red_flags"] else 0.95,
            skills_used=["extract_conditions", "detect_red_flags"],
        )
