# src/ai/agents/cientifico.py
"""Agente Cientifico — gera relatorio com evidencias (RAG + ChromaDB).

Tambem alimenta a base cientifica (C6): quando o RAG nao encontra evidencia
no ChromaDB, o agente busca PubMed em tempo real, registra os artigos
relevantes em knowledge_catalog e ingere os abstracts no ChromaDB para
que a propria chamada — e as proximas — possam usar RAG real.
"""

from __future__ import annotations

import logging
import time

from src.ai.agents.base import BaseAgent, AgentResult

logger = logging.getLogger("cannabia.agents.cientifico")


class AgenteCientifico(BaseAgent):
    agent_name = "cientifico"
    description = "Gera relatorio cientifico com evidencias de PubMed/Cochrane via RAG"

    def _register_skills(self):
        self.register_skill(
            "search_evidence",
            self._search_evidence,
            "Busca evidencias cientificas no ChromaDB",
        )
        self.register_skill(
            "auto_ingest_evidence",
            self._auto_ingest_evidence,
            "Busca PubMed em tempo real, registra no catalogo e ingere abstracts no ChromaDB",
        )
        self.register_skill(
            "generate_report",
            self._generate_report,
            "Gera relatorio cientifico com ou sem RAG",
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
            logger.warning(
                "RAG search_evidence falhou — degradando para sem evidencia (chunks=[]). "
                "Verifique ChromaDB / EmbeddingClient.",
                exc_info=True,
            )
            return {"chunks": [], "has_evidence": False}

    def _auto_ingest_evidence(
        self,
        query_text: str,
        max_results: int = 3,
        created_by: int | None = None,
        **kwargs,
    ) -> dict:
        """
        Gancho C6: cresce a base cientifica em tempo real.

        Roda quando search_evidence retorna 0 chunks. Busca PubMed pelo termo,
        filtra por qualidade leve (titulo, abstract, identificador), registra
        no knowledge_catalog (dedup por DOI/URL) e ingere os abstracts no
        ChromaDB para que a propria chamada possa fazer RAG.
        """
        from src.knowledge.auto_ingest import is_quality_acceptable
        from src.knowledge.pubmed import search_pubmed_articles, fetch_pubmed_abstract

        result = search_pubmed_articles(query=query_text, max_results=max_results)
        articles = result.get("articles", [])
        if not articles:
            return {"articles_seen": 0, "registered": 0, "chunks_added": 0}

        registered = 0
        chunks_added = 0
        embedder = None
        store = None

        for article in articles:
            abstract_resp = fetch_pubmed_abstract(article["pmid"])
            abstract_text = abstract_resp.get("abstract", "")

            article_full = {**article, "abstract": abstract_text}
            if not is_quality_acceptable(article_full):
                # Rate limit do PubMed mesmo quando descartamos.
                time.sleep(0.4)
                continue

            doc_data = {
                "title": article["title"],
                "doc_type": "article",
                "source": "pubmed",
                "source_url": article["source_url"],
                "doi": article.get("doi", ""),
                "category": "cannabis_medicinal",
                "tags": ["auto_ingest_attendance"],
                "authors": article.get("authors", []),
                "journal": article.get("journal", ""),
                "published_date": article.get("published_date"),
                "language": "en",
                "abstract": abstract_text,
                "storage_type": "chromadb",
                "status": "indexed",
            }

            reg = self.register_to_knowledge_base(doc_data, created_by=created_by)
            if not reg.get("registered"):
                # Pode ser duplicate_doi/duplicate_url — segue ingesta no Chroma
                # so se for caso novo. Para duplicatas, pula tambem o Chroma para
                # nao re-embedar.
                time.sleep(0.4)
                continue
            registered += 1

            # Ingere o abstract no ChromaDB como chunk unico para que a propria
            # chamada possa usar RAG sem trigger manual.
            try:
                if embedder is None:
                    from src.knowledge.embeddings import EmbeddingClient
                    from src.knowledge.vector_store import KnowledgeStore
                    embedder = EmbeddingClient()
                    store = KnowledgeStore()
                embedding = embedder.embed_document(abstract_text)
                chunk_id = f"pubmed_{article['pmid']}_chunk_0"
                store.add(
                    chunk_id=chunk_id,
                    embedding=embedding,
                    text=abstract_text,
                    metadata={
                        "title": article["title"],
                        "source": "pubmed",
                        "doi": article.get("doi", ""),
                        "source_url": article["source_url"],
                        "ingested_by": f"agent_{self.agent_name}_auto",
                        "catalog_id": reg.get("catalog_id"),
                    },
                )
                chunks_added += 1
            except (ImportError, ConnectionError, RuntimeError, ValueError) as e:
                # ImportError: EmbeddingClient/KnowledgeStore opcionais;
                # Connection/RuntimeError: ChromaDB offline; ValueError: shape do embedding
                logger.warning("ChromaDB ingest of PubMed abstract failed: %s", e)

            time.sleep(0.4)  # PubMed rate limit (3 req/s max).

        return {
            "articles_seen": len(articles),
            "registered": registered,
            "chunks_added": chunks_added,
        }

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

    @staticmethod
    def _build_query_from_prescription(prescription_result: dict) -> str:
        """
        Sprint 3 Track CFD — query construido a partir de `final_dosage`
        (output clampado do Prescritor), nao do draft do Tratamento.

        Estrategia minimalista + snippet textual rico:
        cannabinoid_ratio + administration_route + spectrum + clinical_rationale[:200]
        """
        final_dosage = prescription_result.get("final_dosage") if isinstance(prescription_result, dict) else None
        if not isinstance(final_dosage, dict):
            return ""

        ratio = str(final_dosage.get("cannabinoid_ratio", ""))
        route = str(final_dosage.get("administration_route", ""))
        spectrum = str(final_dosage.get("spectrum", ""))
        rationale = str(final_dosage.get("clinical_rationale", ""))[:200]

        parts = [ratio, route, spectrum, rationale]
        return " ".join(p for p in parts if p).strip()

    @staticmethod
    def _build_query_from_treatment(treatment_plan: dict, kwargs: dict) -> str:
        """
        Logica legada (pre Sprint 3 CFD): prioriza memory_query, cai para
        campos textuais do treatment_plan. Mantida intacta para preservar
        back-compat com callers que so passam treatment_plan.
        """
        memory_ctx = kwargs.get("_memory_context") or {}
        diary_query = memory_ctx.get("query") if isinstance(memory_ctx, dict) else None
        if diary_query:
            return str(diary_query)

        if isinstance(treatment_plan, dict):
            parts = [
                str(treatment_plan.get("cannabinoid_ratio", "")),
                str(treatment_plan.get("administration_route", "")),
                str(treatment_plan.get("monitoring_plan", "")),
            ]
            joined = " ".join(p for p in parts if p).strip()
            if joined:
                return joined

        import json
        return json.dumps(treatment_plan)[:500] if treatment_plan else "cannabis medicinal"

    @classmethod
    def _build_query(
        cls,
        treatment_plan: dict,
        prescription_result: dict | None = None,
        kwargs: dict | None = None,
    ) -> str:
        """
        Orquestrador da query RAG. Sprint 3 Track CFD decisao Q-CFD-1:
        priorizar `final_dosage` SEMPRE quando presente (nao so quando
        safety_clamp_applied). Fallback pro treatment_plan se prescription
        ausente ou se nao gerou query util.
        """
        kwargs = kwargs or {}

        if prescription_result:
            prescription_query = cls._build_query_from_prescription(prescription_result)
            if prescription_query:
                return prescription_query

        return cls._build_query_from_treatment(treatment_plan, kwargs)

    def execute(self, **kwargs) -> AgentResult:
        treatment_plan = kwargs.get("treatment_plan", {})
        if not treatment_plan:
            return AgentResult(success=False, error="treatment_plan is required")

        # Sprint 3 Track CFD: prescription_result eh opcional (back-compat com
        # legacy pipeline.py que ainda chama com so treatment_plan).
        prescription_result = kwargs.get("prescription_result")

        # Decide query source ANTES de chamar _build_query pra propagar based_on.
        based_on: str | None = None
        if prescription_result:
            candidate = self._build_query_from_prescription(prescription_result)
            if candidate:
                query_text = candidate
                based_on = "final_dosage"

        if based_on is None:
            query_text = self._build_query_from_treatment(treatment_plan, kwargs)
            based_on = "treatment_plan"

        skills_used = ["search_evidence"]

        evidence = self.invoke_skill("search_evidence", query_text=query_text)
        chunks = evidence.get("chunks") or []

        # C6: gancho de crescimento da base. Se ChromaDB nao tem evidencia,
        # o agente busca PubMed em tempo real e ingere o que encontrar.
        auto_ingest_enabled = kwargs.get("auto_ingest_evidence", True)
        ingest_summary = None
        if not chunks and auto_ingest_enabled:
            ingest_summary = self.invoke_skill(
                "auto_ingest_evidence",
                query_text=query_text,
                max_results=kwargs.get("auto_ingest_max", 3),
                created_by=kwargs.get("created_by"),
            )
            skills_used.append("auto_ingest_evidence")

            if ingest_summary.get("chunks_added", 0) > 0:
                evidence = self.invoke_skill("search_evidence", query_text=query_text)
                chunks = evidence.get("chunks") or []

        report_result = self.invoke_skill(
            "generate_report",
            treatment_plan=treatment_plan,
            chunks=chunks,
        )
        skills_used.append("generate_report")

        report = report_result["report"]
        # Sprint 3 Track CFD Q-CFD-5: propaga `based_on` para explicabilidade.
        # Inclui mesmo quando ScientificReport ja foi serializado (dict-shaped).
        if isinstance(report, dict):
            report["based_on"] = based_on
        tokens = report_result.get("tokens", {})

        data = {
            "scientific_report": report,
            "rag_used": report_result.get("rag_used", False),
            "model": report_result.get("model", "unknown"),
            "chunks_used": len(chunks),
            "based_on": based_on,
        }
        if ingest_summary is not None:
            data["auto_ingest"] = ingest_summary

        return AgentResult(
            success=True,
            data=data,
            tokens=tokens if isinstance(tokens, dict) else {},
            confidence=0.85 if report_result.get("rag_used") else 0.7,
            skills_used=skills_used,
        )
