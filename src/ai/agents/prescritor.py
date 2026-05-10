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
        # Sinaliza que weight_kg/prior_cannabis_use vieram de default — anamnese
        # nao coleta esses campos hoje (ver docs/BACKLOG_AGENTE_PRESCRITOR.md).
        defaults_used = bool(kwargs.get("_dosage_defaults_used", False))

        kwargs.pop("_memory_context", None)
        kwargs.pop("_dosage_defaults_used", None)

        result = self.invoke_skill("calculate_dosage", **dosage_input)
        rec = result["recommendation"]
        limits = result.get("safety_limits", {}) or {}
        tokens = result.get("tokens", {})

        confidence = rec.get("confidence_score", 0.0) if isinstance(rec, dict) else 0.0

        cyp450 = list(limits.get("drug_interactions") or [])
        contraind = list(limits.get("contraindications") or [])
        warn = list(limits.get("warnings") or [])

        # Safety clamp ativou efeito real quando Rules Engine detectou
        # interacao ou contraindicacao — dose foi reduzida ou cap aplicado.
        clamp_applied = bool(cyp450 or contraind)
        clamp_reason = None
        if clamp_applied:
            parts = []
            if cyp450:
                parts.append(f"{len(cyp450)} interacao(oes) CYP450")
            if contraind:
                parts.append(f"{len(contraind)} contraindicacao(oes)")
            clamp_reason = "Dose ajustada por: " + " + ".join(parts)

        prescription_result = {
            "final_dosage": rec,
            "safety_clamp_applied": clamp_applied,
            "safety_clamp_reason": clamp_reason,
            "cyp450_interactions": cyp450,
            "monitoring_alerts": list({*contraind, *warn}),
            "rules_engine_summary": {
                "max_cbd_daily_mg": limits.get("max_cbd_daily_mg"),
                "max_thc_daily_mg": limits.get("max_thc_daily_mg"),
                "age_adjustment": limits.get("age_adjustment"),
                "recommended_ratio": limits.get("recommended_ratio"),
                "recommended_route": (
                    limits.get("recommended_route").value
                    if hasattr(limits.get("recommended_route"), "value")
                    else limits.get("recommended_route")
                ),
            },
            "dosage_defaults_used": defaults_used,
            "confidence_score": confidence,
        }

        return AgentResult(
            success=True,
            data={
                "prescription_result": prescription_result,
                "recommendation": rec,
                "treatment_plan": rec,  # Alias for chain compatibility
            },
            tokens=tokens if isinstance(tokens, dict) else {},
            confidence=confidence,
            skills_used=["calculate_dosage"],
        )
