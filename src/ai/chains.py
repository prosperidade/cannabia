import os
import json
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from pydantic import ValidationError

from ai.schemas import ClinicalAnalysis, TreatmentPlan, ScientificReport
from ai.prompts import (
    ANAMNESIS_PROMPT,
    TREATMENT_PLAN_PROMPT,
    SCIENTIFIC_REPORT_PROMPT,
)

# ==========================
# Carrega .env corretamente
# ==========================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY não encontrada no ambiente.")

# ==========================
# Modelo LLM
# ==========================
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key=OPENAI_API_KEY,
)

# ==========================
# Executor com validação
# ==========================
def _run_and_validate(prompt_template: str, schema_model, **kwargs) -> Any:
    """
    Executa o modelo, força JSON e valida com Pydantic.
    """

    prompt = ChatPromptTemplate.from_template(prompt_template)
    chain = prompt | llm

    response = chain.invoke(kwargs)
    raw_output = response.content.strip()

    try:
        parsed_json = json.loads(raw_output)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Resposta do modelo não é JSON válido:\n{raw_output}"
        ) from e

    try:
        validated = schema_model(**parsed_json)
    except ValidationError as e:
        raise ValueError(
            f"JSON não corresponde ao schema esperado:\n{e}"
        ) from e

    return validated


# ==============================
# CHAINS DO PIPELINE
# ==============================

def run_clinical_analysis(**patient_data) -> ClinicalAnalysis:
    return _run_and_validate(
        ANAMNESIS_PROMPT,
        ClinicalAnalysis,
        **patient_data
    )


def run_treatment_plan(clinical_analysis: ClinicalAnalysis) -> TreatmentPlan:
    return _run_and_validate(
        TREATMENT_PLAN_PROMPT,
        TreatmentPlan,
        clinical_analysis=clinical_analysis.model_dump_json()
    )


def run_scientific_report(treatment_plan: TreatmentPlan) -> ScientificReport:
    return _run_and_validate(
        SCIENTIFIC_REPORT_PROMPT,
        ScientificReport,
        treatment_plan=treatment_plan.model_dump_json()
    )

