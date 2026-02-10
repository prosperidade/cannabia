from ai.schemas import (
    AnamnesisInput,
    ClinicalAnalysis,
    TreatmentPlan,
    ScientificReport,
)
from ai.chains import (
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
        clinical_analysis: ClinicalAnalysis = run_clinical_analysis(
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
        treatment_plan: TreatmentPlan = run_treatment_plan(clinical_analysis)

        # =========================
        # ETAPA 3 – Relatório Científico
        # =========================
        scientific_report: ScientificReport = run_scientific_report(treatment_plan)

        return {
            "clinical_analysis": clinical_analysis.dict(),
            "treatment_plan": treatment_plan.dict(),
            "scientific_report": scientific_report.dict(),
        }
