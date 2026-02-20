# src/ai/chains.py

import os
import json
import time
from typing import Tuple, Type
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError
from openai import OpenAI

from src.ai.schemas import ClinicalAnalysis, TreatmentPlan, ScientificReport
from src.ai.prompts import (
    ANAMNESIS_PROMPT,
    TREATMENT_PLAN_PROMPT,
    SCIENTIFIC_REPORT_PROMPT,
)

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL_NAME = "gpt-4o-mini"


def _run_model(prompt: str) -> Tuple[str, dict]:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0,
        messages=[
            {"role": "system", "content": "Responda apenas com JSON válido."},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content

    usage = response.usage

    return content, {
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }


def _run_and_validate(
    prompt_template: str,
    schema_model: Type[BaseModel],
    **kwargs,
):
    prompt = prompt_template.format(**kwargs)

    raw_output, tokens = _run_model(prompt)

    try:
        parsed_json = json.loads(raw_output)
    except json.JSONDecodeError:
        raise ValueError(f"Modelo retornou JSON inválido:\n{raw_output}")

    try:
        validated = schema_model(**parsed_json)
    except ValidationError as e:
        raise ValueError(f"JSON não corresponde ao schema:\n{e}")

    return validated, tokens


def run_clinical_analysis(**patient_data):
    for k, v in patient_data.items():
        if isinstance(v, list):
            patient_data[k] = "\n".join([f"- {x}" for x in v])
        else:
            patient_data[k] = str(v)

    return _run_and_validate(ANAMNESIS_PROMPT, ClinicalAnalysis, **patient_data)


def run_treatment_plan(clinical_analysis: ClinicalAnalysis):
    return _run_and_validate(
        TREATMENT_PLAN_PROMPT,
        TreatmentPlan,
        clinical_analysis=clinical_analysis.model_dump_json(),
    )


def run_scientific_report(treatment_plan: TreatmentPlan):
    return _run_and_validate(
        SCIENTIFIC_REPORT_PROMPT,
        ScientificReport,
        treatment_plan=treatment_plan.model_dump_json(),
    )
