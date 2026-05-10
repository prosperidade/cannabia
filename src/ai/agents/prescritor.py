# src/ai/agents/prescritor.py
"""Agente Prescritor — calcula dosagem segura com rules engine + LLM + safety clamp."""

from __future__ import annotations
from src.ai.agents.base import BaseAgent, AgentResult


class AgentePrescritor(BaseAgent):
    agent_name = "prescritor"
    description = "Calcula dosagem CBD/THC com rules engine, LLM e safety clamp"

    def _register_skills(self):
        self.register_skill(
            "calculate_safety_limits",
            self._safety_limits,
            "Calcula limites de segurança determinísticos (rules engine)",
        )
        self.register_skill(
            "calculate_dosage",
            self._calculate_dosage,
            "Gera recomendação de dosagem completa (rules + LLM + clamp)",
        )
        self.register_skill(
            "check_interactions",
            self._check_interactions,
            "Verifica interações medicamentosas CYP450",
        )

    def _safety_limits(self, **dosage_input) -> dict:
        from src.ai.prescriber import calculate_safety_limits
        from src.ai.schemas import DosageInput
        di = DosageInput(**dosage_input)
        limits = calculate_safety_limits(di)
        return {"safety_limits": limits.__dict__ if hasattr(limits, "__dict__") else limits}

    def _calculate_dosage(self, **dosage_input) -> dict:
        from src.ai.prescriber import run_prescriber
        from src.ai.schemas import DosageInput
        di = DosageInput(**dosage_input)
        recommendation, safety_limits, tokens = run_prescriber(di)
        return {
            "recommendation": recommendation.model_dump() if hasattr(recommendation, "model_dump") else recommendation,
            "safety_limits": safety_limits.__dict__ if hasattr(safety_limits, "__dict__") else safety_limits,
            "tokens": tokens,
        }

    def _check_interactions(self, medications: list, **kwargs) -> dict:
        from src.ai.prescriber import _detect_drug_interactions
        warnings, dose_multiplier = _detect_drug_interactions(medications)
        return {
            "interactions": warnings,
            "has_interactions": bool(warnings),
            "dose_multiplier": dose_multiplier,
        }

    def execute(self, **kwargs) -> AgentResult:
        dosage_input = kwargs.get("dosage_input", kwargs)

        # MemPalace recall/remember removidos em Track C.2 — agentes nao tem
        # mais memoria persistente automatica. Skip do _memory_context que
        # call sites legados ainda passam.
        kwargs.pop("_memory_context", None)

        result = self.invoke_skill("calculate_dosage", **dosage_input)
        rec = result["recommendation"]
        tokens = result.get("tokens", {})

        confidence = rec.get("confidence_score", 0.0) if isinstance(rec, dict) else 0.0

        return AgentResult(
            success=True,
            data={
                "recommendation": rec,
                "treatment_plan": rec,  # Alias for chain compatibility
            },
            tokens=tokens if isinstance(tokens, dict) else {},
            confidence=confidence,
            skills_used=["calculate_dosage"],
        )
