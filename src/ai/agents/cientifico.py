# src/ai/agents/cientifico.py
"""Agente Científico — gera relatório com evidências (RAG + ChromaDB)."""

from __future__ import annotations
from src.ai.agents.base import BaseAgent, AgentResult


class AgenteCientifico(BaseAgent):
    palace_room = "pipeline_cientifico"
    agent_name = "cientifico"
    description = "Gera relatório científico com evidências de PubMed/Cochrane via RAG"

    def _register_skills(self):
        self.register_skill(
            "search_evidence",
            self._search_evidence,
            "Busca evidências científicas no ChromaDB",
        )
        self.register_skill(
            "generate_report",
            self._generate_report,
            "Gera relatório científico com ou sem RAG",
        )

    def _search_evidence(self, query_text: str, n_results: int = 5, **kwargs) -> dict:
        try:
            from src.knowledge.embeddings import EmbeddingClient
            from src.knowledge.vector_store import KnowledgeStore
            embedder = EmbeddingClient()
            store = KnowledgeStore()
            if store.count() == 0:
                return {"chunks": [], "has_evidence": False}
            query_vec = embedder.embed_query(query_text)
            chunks = store.query(query_vec, n_results=n_results)
            return {"chunks": chunks, "has_evidence": bool(chunks)}
        except Exception:
            return {"chunks": [], "has_evidence": False}

    def _generate_report(self, treatment_plan: dict, chunks: list = None, **kwargs) -> dict:
        from src.ai.schemas import TreatmentPlan
        tp = TreatmentPlan(**treatment_plan) if isinstance(treatment_plan, dict) else treatment_plan

        if chunks:
            from src.ai.chains import run_scientific_report_rag
            report, tokens = run_scientific_report_rag(tp, chunks)
            return {"report": report.model_dump() if hasattr(report, "model_dump") else report,
                    "tokens": tokens, "model": "gemini-1.5-flash", "rag_used": True}
        else:
            from src.ai.chains import run_scientific_report
            report, tokens = run_scientific_report(tp)
            return {"report": report.model_dump() if hasattr(report, "model_dump") else report,
                    "tokens": tokens, "model": "gpt-4o-mini", "rag_used": False}

    def execute(self, **kwargs) -> AgentResult:
        treatment_plan = kwargs.get("treatment_plan", {})
        if not treatment_plan:
            return AgentResult(success=False, error="treatment_plan is required")

        import json
        query_text = json.dumps(treatment_plan) if isinstance(treatment_plan, dict) else str(treatment_plan)

        # Search evidence
        evidence = self.invoke_skill("search_evidence", query_text=query_text)

        # Generate report
        report_result = self.invoke_skill(
            "generate_report",
            treatment_plan=treatment_plan,
            chunks=evidence.get("chunks"),
        )

        report = report_result["report"]
        tokens = report_result.get("tokens", {})

        return AgentResult(
            success=True,
            data={
                "scientific_report": report,
                "rag_used": report_result.get("rag_used", False),
                "model": report_result.get("model", "unknown"),
                "chunks_used": len(evidence.get("chunks", [])),
            },
            tokens=tokens if isinstance(tokens, dict) else {},
            confidence=0.85 if report_result.get("rag_used") else 0.7,
            skills_used=["search_evidence", "generate_report"],
        )
