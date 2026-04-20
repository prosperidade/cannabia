from __future__ import annotations

import os
from typing import Any, Dict, Protocol

from src.ai.agents import AgenteAnamnese, AgenteCientifico, AgenteTratamento
from src.ai.pipeline import CannabIAPipeline
from src.ai.schemas import AnamnesisInput
from src.infra.metrics import measure


class ClinicalFlow(Protocol):
    def run(self, anamnesis_data: AnamnesisInput) -> Dict[str, Any]:
        ...


class SpecialistClinicalFlow:
    """Fluxo clínico explícito por especialistas, sem depender do Orchestrator."""

    def __init__(self) -> None:
        self.anamnese = AgenteAnamnese()
        self.tratamento = AgenteTratamento()
        self.cientifico = AgenteCientifico()

    @staticmethod
    def _token_triplet(tokens: Dict[str, Any] | None) -> Dict[str, int]:
        payload = tokens or {}
        return {
            "input": int(payload.get("input_tokens", 0) or 0),
            "output": int(payload.get("output_tokens", 0) or 0),
            "total": int(payload.get("total_tokens", 0) or 0),
        }

    def run(self, anamnesis_data: AnamnesisInput) -> Dict[str, Any]:
        patient_data = anamnesis_data.model_dump()
        memory_query = " | ".join(
            [
                patient_data.get("main_complaint", ""),
                ", ".join(patient_data.get("symptoms", [])),
            ]
        ).strip(" |")

        with measure("ai.stage.clinical"):
            anamnese_result = self.anamnese.run(
                patient_data=patient_data,
                _memory_query=memory_query or None,
            )
        if not anamnese_result.success:
            raise RuntimeError(anamnese_result.error or "Falha na etapa de anamnese.")

        clinical_analysis = anamnese_result.data["clinical_analysis"]
        treatment_query = " | ".join(
            [
                patient_data.get("main_complaint", ""),
                ", ".join(clinical_analysis.get("probable_conditions", [])),
            ]
        ).strip(" |")

        with measure("ai.stage.treatment"):
            tratamento_result = self.tratamento.run(
                clinical_analysis=clinical_analysis,
                _memory_query=treatment_query or None,
            )
        if not tratamento_result.success:
            raise RuntimeError(tratamento_result.error or "Falha na etapa de tratamento.")

        treatment_plan = tratamento_result.data["treatment_plan"]
        scientific_query = " | ".join(
            [
                patient_data.get("main_complaint", ""),
                str(treatment_plan.get("cannabinoid_ratio", "")),
            ]
        ).strip(" |")

        with measure("ai.stage.report"):
            cientifico_result = self.cientifico.run(
                treatment_plan=treatment_plan,
                _memory_query=scientific_query or None,
            )
        if not cientifico_result.success:
            raise RuntimeError(cientifico_result.error or "Falha na etapa científica.")

        token_1 = self._token_triplet(anamnese_result.tokens)
        token_2 = self._token_triplet(tratamento_result.tokens)
        token_3 = self._token_triplet(cientifico_result.tokens)

        return {
            "clinical_analysis": clinical_analysis,
            "treatment_plan": treatment_plan,
            "scientific_report": cientifico_result.data["scientific_report"],
            "rag_chunks_used": cientifico_result.data.get("chunks_used", 0),
            "report_model": cientifico_result.data.get("model", "unknown"),
            "token_usage": {
                "input": token_1["input"] + token_2["input"] + token_3["input"],
                "output": token_1["output"] + token_2["output"] + token_3["output"],
                "total": token_1["total"] + token_2["total"] + token_3["total"],
            },
            "execution_mode": "specialists",
            "specialists_used": [
                self.anamnese.agent_name,
                self.tratamento.agent_name,
                self.cientifico.agent_name,
            ],
        }


def build_clinical_flow(mode: str | None = None) -> ClinicalFlow:
    selected_mode = (mode or os.getenv("AI_EXECUTION_MODE", "specialists")).strip().lower()
    if selected_mode == "legacy":
        return CannabIAPipeline()
    return SpecialistClinicalFlow()
