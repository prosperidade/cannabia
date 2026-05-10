from __future__ import annotations

import os
import time
from typing import Any, Dict, Protocol

from src.ai.agents import AgenteAnamnese, AgenteCientifico, AgenteTratamento
from src.ai.agents.prescritor import AgentePrescritor
from src.ai.pipeline import CannabIAPipeline
from src.ai.schemas import AnamnesisInput
from src.infra.metrics import measure


# Defaults aplicados quando AnamnesisInput nao carrega o campo. Anamnese
# atual nao coleta peso nem uso previo de cannabis — gap conhecido,
# documentado em docs/BACKLOG_AGENTE_PRESCRITOR.md (Sprint 2 estende UI).
DOSAGE_DEFAULT_WEIGHT_KG = 70.0
DOSAGE_DEFAULT_PRIOR_USE = False


class ClinicalFlow(Protocol):
    def run(self, anamnesis_data: AnamnesisInput) -> Dict[str, Any]:
        ...


class SpecialistClinicalFlow:
    """Fluxo clínico explícito por especialistas, sem depender do Orchestrator."""

    def __init__(self) -> None:
        self.anamnese = AgenteAnamnese()
        self.tratamento = AgenteTratamento()
        self.prescritor = AgentePrescritor()
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

        t0 = time.perf_counter()
        with measure("ai.stage.clinical"):
            anamnese_result = self.anamnese.run(
                patient_data=patient_data,
                _memory_query=memory_query or None,
            )
        clinical_ms = int((time.perf_counter() - t0) * 1000)
        if not anamnese_result.success:
            raise RuntimeError(anamnese_result.error or "Falha na etapa de anamnese.")

        clinical_analysis = anamnese_result.data["clinical_analysis"]
        treatment_query = " | ".join(
            [
                patient_data.get("main_complaint", ""),
                ", ".join(clinical_analysis.get("probable_conditions", [])),
            ]
        ).strip(" |")

        t0 = time.perf_counter()
        with measure("ai.stage.treatment"):
            tratamento_result = self.tratamento.run(
                clinical_analysis=clinical_analysis,
                _memory_query=treatment_query or None,
            )
        treatment_ms = int((time.perf_counter() - t0) * 1000)
        if not tratamento_result.success:
            raise RuntimeError(tratamento_result.error or "Falha na etapa de tratamento.")

        treatment_plan = tratamento_result.data["treatment_plan"]

        # ── Prescritor (Track C.1) ────────────────────────────────────────
        # Roda APOS Tratamento e ANTES de Cientifico. Recebe campos do
        # patient_data + clinical_analysis para construir DosageInput.
        # weight_kg e prior_cannabis_use sao defaults (anamnese nao coleta).
        weight_kg = patient_data.get("weight_kg") or DOSAGE_DEFAULT_WEIGHT_KG
        prior_use = patient_data.get("prior_cannabis_use", DOSAGE_DEFAULT_PRIOR_USE)
        defaults_used = (
            patient_data.get("weight_kg") is None
            or patient_data.get("prior_cannabis_use") is None
        )
        risk_level = clinical_analysis.get("risk_level") or "moderado"
        if isinstance(risk_level, str):
            risk_level = risk_level.lower().strip()
            if risk_level not in {"baixo", "moderado", "alto"}:
                risk_level = "moderado"

        dosage_input = {
            "patient_name": patient_data.get("patient_name", ""),
            "age": int(patient_data.get("age", 0) or 0),
            "weight_kg": float(weight_kg),
            "height_cm": patient_data.get("height_cm"),
            "main_complaint": patient_data.get("main_complaint", ""),
            "symptoms": list(patient_data.get("symptoms") or []),
            "conditions": list(clinical_analysis.get("probable_conditions") or []),
            "current_medications": list(patient_data.get("current_medications") or []),
            "allergies": list(patient_data.get("allergies") or []),
            "medical_history": patient_data.get("medical_history"),
            "prior_cannabis_use": bool(prior_use),
            "risk_level": risk_level,
        }

        t0 = time.perf_counter()
        with measure("ai.stage.prescription"):
            prescritor_result = self.prescritor.run(
                dosage_input=dosage_input,
                _dosage_defaults_used=defaults_used,
            )
        prescription_ms = int((time.perf_counter() - t0) * 1000)
        if not prescritor_result.success:
            raise RuntimeError(prescritor_result.error or "Falha na etapa de prescricao.")

        prescription_result = prescritor_result.data["prescription_result"]

        scientific_query = " | ".join(
            [
                patient_data.get("main_complaint", ""),
                str(treatment_plan.get("cannabinoid_ratio", "")),
            ]
        ).strip(" |")

        t0 = time.perf_counter()
        with measure("ai.stage.report"):
            cientifico_result = self.cientifico.run(
                treatment_plan=treatment_plan,
                _memory_query=scientific_query or None,
            )
        report_ms = int((time.perf_counter() - t0) * 1000)
        if not cientifico_result.success:
            raise RuntimeError(cientifico_result.error or "Falha na etapa científica.")

        token_1 = self._token_triplet(anamnese_result.tokens)
        token_2 = self._token_triplet(tratamento_result.tokens)
        token_p = self._token_triplet(prescritor_result.tokens)
        token_3 = self._token_triplet(cientifico_result.tokens)

        # Modelo por etapa: anamnese e tratamento usam OpenAI gpt-4o-mini
        # (chains.OPENAI_MODEL); cientifico usa o reportado pelo agente (Gemini
        # quando RAG ativo, gpt-4o-mini no fallback).
        report_model = cientifico_result.data.get("model", "gpt-4o-mini")

        return {
            "clinical_analysis": clinical_analysis,
            "treatment_plan": treatment_plan,
            "prescription_result": prescription_result,
            "scientific_report": cientifico_result.data["scientific_report"],
            "rag_chunks_used": cientifico_result.data.get("chunks_used", 0),
            "report_model": report_model,
            "token_usage": {
                "input": token_1["input"] + token_2["input"] + token_p["input"] + token_3["input"],
                "output": token_1["output"] + token_2["output"] + token_p["output"] + token_3["output"],
                "total": token_1["total"] + token_2["total"] + token_p["total"] + token_3["total"],
            },
            # tokens_per_stage e o input correto para cost-per-stage em
            # service.py — cada etapa pode usar modelo diferente.
            "tokens_per_stage": {
                "clinical": {
                    "model": "gpt-4o-mini",
                    "tokens": {"input": token_1["input"], "output": token_1["output"]},
                },
                "treatment": {
                    "model": "gpt-4o-mini",
                    "tokens": {"input": token_2["input"], "output": token_2["output"]},
                },
                "prescription": {
                    "model": "gpt-4o-mini",
                    "tokens": {"input": token_p["input"], "output": token_p["output"]},
                },
                "report": {
                    "model": report_model,
                    "tokens": {"input": token_3["input"], "output": token_3["output"]},
                },
            },
            "timings_ms": {
                "clinical": clinical_ms,
                "treatment": treatment_ms,
                "prescription": prescription_ms,
                "report": report_ms,
            },
            "execution_mode": "specialists",
            "specialists_used": [
                self.anamnese.agent_name,
                self.tratamento.agent_name,
                self.prescritor.agent_name,
                self.cientifico.agent_name,
            ],
        }


def build_clinical_flow(mode: str | None = None) -> ClinicalFlow:
    selected_mode = (mode or os.getenv("AI_EXECUTION_MODE", "specialists")).strip().lower()
    if selected_mode == "legacy":
        return CannabIAPipeline()
    return SpecialistClinicalFlow()
