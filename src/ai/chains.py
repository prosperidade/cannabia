# src/ai/chains.py

import json
import logging
import os
from typing import List, Tuple, Type

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from src.ai.schemas import ClinicalAnalysis, ScientificReport, TreatmentPlan
from src.ai.prompts import (
    ANAMNESIS_PROMPT,
    SCIENTIFIC_REPORT_PROMPT,
    SCIENTIFIC_REPORT_RAG_PROMPT,
    TREATMENT_PLAN_PROMPT,
)

load_dotenv()
logger = logging.getLogger("cannabia.ai")

# ── Clientes ──────────────────────────────────────────────────────────────────
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
gemini_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

OPENAI_MODEL = "gpt-4o-mini"
GEMINI_MODEL = "gemini-1.5-flash"


# ══════════════════════════════════════════════════════════════════════════════
# OPENAI — helper interno (Etapas 1 e 2)
# ══════════════════════════════════════════════════════════════════════════════

def _run_openai(prompt: str) -> Tuple[str, dict]:
    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": "Responda apenas com JSON válido."},
            {"role": "user",   "content": prompt},
        ],
    )
    content = response.choices[0].message.content
    usage   = response.usage
    return content, {
        "input_tokens":  usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "total_tokens":  usage.total_tokens,
    }


def _run_and_validate(
    prompt_template: str,
    schema_model: Type[BaseModel],
    **kwargs,
):
    prompt = prompt_template.format(**kwargs)
    raw_output, tokens = _run_openai(prompt)
    try:
        parsed_json = json.loads(raw_output)
    except json.JSONDecodeError:
        raise ValueError(f"Modelo retornou JSON inválido:\n{raw_output}")
    try:
        validated = schema_model(**parsed_json)
    except ValidationError as e:
        raise ValueError(f"JSON não corresponde ao schema:\n{e}")
    return validated, tokens


# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 1 — Análise Clínica (OpenAI)
# ══════════════════════════════════════════════════════════════════════════════

def run_clinical_analysis(**patient_data):
    for k, v in patient_data.items():
        patient_data[k] = "\n".join([f"- {x}" for x in v]) if isinstance(v, list) else str(v)
    return _run_and_validate(ANAMNESIS_PROMPT, ClinicalAnalysis, **patient_data)


# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 2 — Plano Terapêutico (OpenAI)
# ══════════════════════════════════════════════════════════════════════════════

def run_treatment_plan(clinical_analysis: ClinicalAnalysis):
    return _run_and_validate(
        TREATMENT_PLAN_PROMPT,
        TreatmentPlan,
        clinical_analysis=clinical_analysis.model_dump_json(),
    )


# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 3 — Relatório Científico sem RAG (fallback / OpenAI)
# Mantido para compatibilidade quando o ChromaDB estiver vazio.
# ══════════════════════════════════════════════════════════════════════════════

def run_scientific_report(treatment_plan: TreatmentPlan):
    return _run_and_validate(
        SCIENTIFIC_REPORT_PROMPT,
        ScientificReport,
        treatment_plan=treatment_plan.model_dump_json(),
    )


# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 3 (RAG) — Relatório Científico com Gemini 1.5 Flash + contexto vetorial
# ══════════════════════════════════════════════════════════════════════════════

def _format_rag_context(chunks: List[dict]) -> str:
    """Formata os chunks recuperados do ChromaDB em texto estruturado para o prompt."""
    if not chunks:
        return "Nenhuma referência científica disponível no banco vetorial."

    lines = []
    for i, chunk in enumerate(chunks, 1):
        meta  = chunk.get("metadata", {})
        title = meta.get("title",  "Título não informado")
        doi   = meta.get("doi",    "N/A")
        score = chunk.get("similarity_score", 0)
        text  = chunk.get("text", "")
        lines.append(
            f"[{i}] Título: {title} | DOI: {doi} | Relevância: {score:.2f}\n{text}"
        )

    return "\n\n---\n\n".join(lines)


def run_scientific_report_rag(
    treatment_plan: TreatmentPlan,
    rag_chunks: List[dict],
) -> Tuple[ScientificReport, dict]:
    """
    Gera o Relatório Científico usando Google Gemini 1.5 Flash,
    embasado nos chunks recuperados do ChromaDB.
    """
    scientific_context = _format_rag_context(rag_chunks)

    prompt = SCIENTIFIC_REPORT_RAG_PROMPT.format(
        treatment_plan=treatment_plan.model_dump_json(),
        scientific_context=scientific_context,
    )

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
        ),
    )

    raw_output = response.text.strip()

    try:
        parsed_json = json.loads(raw_output)
    except json.JSONDecodeError:
        raise ValueError(f"Gemini retornou JSON inválido:\n{raw_output}")

    try:
        validated = ScientificReport(**parsed_json)
    except ValidationError as e:
        raise ValueError(f"JSON do Gemini não corresponde ao schema:\n{e}")

    # Gemini expõe uso de tokens em usage_metadata
    usage = response.usage_metadata
    tokens = {
        "input_tokens":  getattr(usage, "prompt_token_count",     0) or 0,
        "output_tokens": getattr(usage, "candidates_token_count", 0) or 0,
        "total_tokens":  getattr(usage, "total_token_count",      0) or 0,
    }

    logger.info(
        "Gemini RAG report gerado: %d tokens (contexto: %d chunks).",
        tokens["total_tokens"],
        len(rag_chunks),
    )

    return validated, tokens
