# src/ai/pipeline.py

from src.ai.schemas import (
    AnamnesisInput,
    ClinicalAnalysis,
    TreatmentPlan,
    ScientificReport,
)
from src.ai.chains import (
    run_clinical_analysis,
    run_treatment_plan,
    run_scientific_report,
)


class CannabIAPipeline:
    """
    Pipeline clínico estruturado:
    1. Análise clínica
    2. Plano terapêutico
    3. Relatório científico
    """

    def run(self, anamnesis_data: AnamnesisInput):
        # =========================
        # ETAPA 1 – Análise Clínica
        # =========================
        clinical_analysis, tokens_1 = run_clinical_analysis(
            patient_name=anamnesis_data.patient_name,
            age=anamnesis_data.age,
            main_complaint=anamnesis_data.main_complaint,
            symptoms=anamnesis_data.symptoms,
            current_medications=anamnesis_data.current_medications,
            allergies=anamnesis_data.allergies,
            medical_history=anamnesis_data.medical_history,
        )

        # =========================
        # ETAPA 2 – Plano Terapêutico
        # =========================
        treatment_plan, tokens_2 = run_treatment_plan(clinical_analysis)

        # =========================
        # ETAPA 3 – Relatório Científico
        # =========================
        scientific_report, tokens_3 = run_scientific_report(treatment_plan)

        # soma tokens
        token_usage = {
            "input": (tokens_1["input_tokens"] + tokens_2["input_tokens"] + tokens_3["input_tokens"]),
            "output": (tokens_1["output_tokens"] + tokens_2["output_tokens"] + tokens_3["output_tokens"]),
            "total": (tokens_1["total_tokens"] + tokens_2["total_tokens"] + tokens_3["total_tokens"]),
        }

        return {
            "clinical_analysis": clinical_analysis.model_dump(),
            "treatment_plan": treatment_plan.model_dump(),
            "scientific_report": scientific_report.model_dump(),
            "token_usage": token_usage,
        }
