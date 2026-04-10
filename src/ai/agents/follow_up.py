# src/ai/agents/follow_up.py
"""Agente FollowUp — gerencia retornos, diário de sintomas e ajustes de dosagem."""

from __future__ import annotations
from src.ai.agents.base import BaseAgent, AgentResult


class AgenteFollowUp(BaseAgent):
    palace_room = "crm_telemetria"
    agent_name = "follow_up"
    description = "Gerencia retornos, analisa diário de sintomas e sugere ajustes de dosagem"

    def _register_skills(self):
        self.register_skill(
            "analyze_diary",
            self._analyze_diary,
            "Analisa entradas do diário de sintomas do paciente",
        )
        self.register_skill(
            "suggest_adjustment",
            self._suggest_adjustment,
            "Sugere ajuste de dosagem baseado na evolução",
        )
        self.register_skill(
            "schedule_return",
            self._schedule_return,
            "Determina data de retorno baseado no protocolo",
        )

    def _analyze_diary(self, diary_entries: list, **kwargs) -> dict:
        if not diary_entries:
            return {"trend": "insufficient_data", "avg_scores": {}, "improving": None}

        scores = [e.get("overall_score", 0) for e in diary_entries if e.get("overall_score")]
        pains = [e.get("pain_level", 0) for e in diary_entries if e.get("pain_level") is not None]
        sleeps = [e.get("sleep_quality", 0) for e in diary_entries if e.get("sleep_quality") is not None]

        avg = {
            "overall": round(sum(scores) / len(scores), 1) if scores else 0,
            "pain": round(sum(pains) / len(pains), 1) if pains else 0,
            "sleep": round(sum(sleeps) / len(sleeps), 1) if sleeps else 0,
        }

        # Trend: compare first half vs second half
        mid = len(scores) // 2
        if mid > 0:
            first_half = sum(scores[:mid]) / mid
            second_half = sum(scores[mid:]) / (len(scores) - mid)
            improving = second_half > first_half
            trend = "improving" if improving else "stable_or_worsening"
        else:
            improving = None
            trend = "insufficient_data"

        return {"trend": trend, "avg_scores": avg, "improving": improving, "entries_analyzed": len(diary_entries)}

    def _suggest_adjustment(self, diary_analysis: dict, current_dosage: dict = None, **kwargs) -> dict:
        trend = diary_analysis.get("trend", "insufficient_data")
        avg = diary_analysis.get("avg_scores", {})

        suggestion = {
            "action": "maintain",
            "reason": "Dados insuficientes para ajuste",
            "confidence": 0.5,
        }

        if trend == "improving" and avg.get("overall", 0) >= 7:
            suggestion = {
                "action": "maintain",
                "reason": "Paciente em melhora consistente. Manter dosagem atual.",
                "confidence": 0.85,
            }
        elif trend == "improving" and avg.get("overall", 0) < 7:
            suggestion = {
                "action": "increase",
                "reason": "Melhora parcial. Considerar aumento gradual conforme protocolo START LOW GO SLOW.",
                "confidence": 0.7,
            }
        elif trend == "stable_or_worsening" and avg.get("pain", 0) > 5:
            suggestion = {
                "action": "increase",
                "reason": "Dor persistente acima de 5/10. Reavaliar dosagem e considerar ajuste de ratio.",
                "confidence": 0.75,
            }
        elif trend == "stable_or_worsening" and avg.get("overall", 0) >= 7:
            suggestion = {
                "action": "maintain",
                "reason": "Estável com boa qualidade de vida. Manter protocolo.",
                "confidence": 0.8,
            }

        return suggestion

    def _schedule_return(self, treatment_phase: str = "manutencao", **kwargs) -> dict:
        phase_days = {
            "inicial": 7,
            "titulacao": 14,
            "ajuste": 14,
            "manutencao": 30,
        }
        days = phase_days.get(treatment_phase, 30)
        return {"return_in_days": days, "phase": treatment_phase}

    def execute(self, **kwargs) -> AgentResult:
        diary_entries = kwargs.get("diary_entries", [])
        current_dosage = kwargs.get("current_dosage")
        treatment_phase = kwargs.get("treatment_phase", "manutencao")

        skills_used = []

        # Analyze diary
        analysis = self.invoke_skill("analyze_diary", diary_entries=diary_entries)
        skills_used.append("analyze_diary")

        # Suggest adjustment
        adjustment = self.invoke_skill(
            "suggest_adjustment",
            diary_analysis=analysis,
            current_dosage=current_dosage,
        )
        skills_used.append("suggest_adjustment")

        # Schedule return
        schedule = self.invoke_skill("schedule_return", treatment_phase=treatment_phase)
        skills_used.append("schedule_return")

        # Remember patterns
        if analysis.get("trend") != "insufficient_data":
            self.remember(
                f"Diary analysis: trend={analysis['trend']} "
                f"avg_overall={analysis['avg_scores'].get('overall', 0)} "
                f"adjustment={adjustment['action']}"
            )

        return AgentResult(
            success=True,
            data={
                "diary_analysis": analysis,
                "adjustment_suggestion": adjustment,
                "return_schedule": schedule,
            },
            confidence=adjustment.get("confidence", 0.5),
            skills_used=skills_used,
        )
