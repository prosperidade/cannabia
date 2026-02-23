# src/ai/pipeline.py

import logging

from src.ai.schemas import AnamnesisInput
from src.ai.chains import (
    run_clinical_analysis,
    run_treatment_plan,
    run_scientific_report,
    run_scientific_report_rag,
)
from src.knowledge.vector_store import KnowledgeStore
from src.knowledge.embeddings import EmbeddingClient

logger = logging.getLogger("cannabia.ai")


class CannabIAPipeline:
    """
    Pipeline clínico estruturado:

    Etapa 1   — Análise Clínica       (OpenAI gpt-4o-mini)
    Etapa 2   — Plano Terapêutico     (OpenAI gpt-4o-mini)
    Etapa 2.5 — RAG Lookup            (ChromaDB + Google text-embedding-004)
    Etapa 3   — Relatório Científico  (Gemini 1.5 Flash + contexto RAG)
                Fallback              (gpt-4o-mini, quando ChromaDB estiver vazio)
    """

    def __init__(self) -> None:
        self._store    = KnowledgeStore()
        self._embedder = EmbeddingClient()

    def run(self, anamnesis_data: AnamnesisInput) -> dict:

        # ═══════════════════════════════════════════════════════════
        # ETAPA 1 — Análise Clínica (OpenAI)
        # ═══════════════════════════════════════════════════════════
        clinical_analysis, tokens_1 = run_clinical_analysis(
            patient_name=anamnesis_data.patient_name,
            age=anamnesis_data.age,
            main_complaint=anamnesis_data.main_complaint,
            symptoms=anamnesis_data.symptoms,
            current_medications=anamnesis_data.current_medications,
            allergies=anamnesis_data.allergies,
            medical_history=anamnesis_data.medical_history,
        )

        # ═══════════════════════════════════════════════════════════
        # ETAPA 2 — Plano Terapêutico (OpenAI)
        # ═══════════════════════════════════════════════════════════
        treatment_plan, tokens_2 = run_treatment_plan(clinical_analysis)

        # ═══════════════════════════════════════════════════════════
        # ETAPA 2.5 — RAG Lookup (ChromaDB)
        # Vetoriza o TreatmentPlan e busca os artigos mais similares.
        # Se o banco estiver vazio ou falhar, usa fallback silencioso.
        # ═══════════════════════════════════════════════════════════
        rag_chunks = []
        use_rag    = False

        if self._store.count() > 0:
            try:
                query_text = treatment_plan.model_dump_json()
                query_vec  = self._embedder.embed_query(query_text)
                rag_chunks = self._store.query(query_vec, n_results=5)
                use_rag    = True
                logger.info("RAG lookup: %d chunks recuperados do ChromaDB.", len(rag_chunks))
            except Exception:
                logger.warning(
                    "RAG lookup falhou — usando fallback OpenAI para relatório.",
                    exc_info=True,
                )
        else:
            logger.info("ChromaDB vazio — usando fallback OpenAI para Etapa 3.")

        # ═══════════════════════════════════════════════════════════
        # ETAPA 3 — Relatório Científico
        # RAG path:      Gemini 1.5 Flash + contexto vetorial
        # Fallback path: gpt-4o-mini (banco vazio ou erro de RAG)
        # ═══════════════════════════════════════════════════════════
        if use_rag:
            scientific_report, tokens_3 = run_scientific_report_rag(treatment_plan, rag_chunks)
            report_model = "gemini-1.5-flash"
        else:
            scientific_report, tokens_3 = run_scientific_report(treatment_plan)
            report_model = "gpt-4o-mini"

        # Consolida uso de tokens das 3 etapas OpenAI/Gemini
        token_usage = {
            "input":  tokens_1["input_tokens"]  + tokens_2["input_tokens"]  + tokens_3["input_tokens"],
            "output": tokens_1["output_tokens"] + tokens_2["output_tokens"] + tokens_3["output_tokens"],
            "total":  tokens_1["total_tokens"]  + tokens_2["total_tokens"]  + tokens_3["total_tokens"],
        }

        return {
            "clinical_analysis": clinical_analysis.model_dump(),
            "treatment_plan":    treatment_plan.model_dump(),
            "scientific_report": scientific_report.model_dump(),
            "rag_chunks_used":   len(rag_chunks),
            "report_model":      report_model,
            "token_usage":       token_usage,
        }
