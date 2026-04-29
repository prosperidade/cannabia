"""Testes do gancho C6 no AgenteCientifico (auto-ingest de evidencia PubMed)."""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from src.ai.agents.cientifico import AgenteCientifico


# ── _build_query ──


def test_build_query_prefers_memory_context_query():
    plan = {"cannabinoid_ratio": "1:1", "monitoring_plan": "monthly"}
    kwargs = {"_memory_context": {"query": "epilepsy refractory CBD"}}

    query = AgenteCientifico._build_query(plan, kwargs)

    assert query == "epilepsy refractory CBD"


def test_build_query_falls_back_to_plan_text_fields():
    plan = {
        "cannabinoid_ratio": "20:1 CBD/THC",
        "administration_route": "oral",
        "monitoring_plan": "weekly seizure log",
    }
    query = AgenteCientifico._build_query(plan, {})

    assert "20:1" in query
    assert "oral" in query
    assert "seizure log" in query


def test_build_query_default_when_plan_empty():
    query = AgenteCientifico._build_query({}, {})
    assert query  # nao retorna string vazia


# ── execute() with chunks present ──


def _make_treatment_plan() -> Dict[str, Any]:
    return {
        "cannabinoid_ratio": "10:1",
        "suggested_dosage": "5mg/kg/dia",
        "administration_route": "oral",
        "monitoring_plan": "monthly",
        "precautions": ["evitar dirigir"],
    }


def _patch_skills(agent: AgenteCientifico, **handlers):
    """
    Patch dos handlers registrados em agent._skills.

    Necessario porque invoke_skill() resolve o callable a partir de
    agent._skills[<name>].handler, capturado em __init__ como bound method.
    Patchar diretamente o atributo do agente (patch.object(agent, "_search...")
    nao surte efeito.
    """
    patches = []
    for name, handler in handlers.items():
        skill = agent._skills[name]
        p = patch.object(skill, "handler", handler)
        patches.append(p)
    return patches


def _enter_all(patches):
    [p.start() for p in patches]


def _exit_all(patches):
    for p in reversed(patches):
        p.stop()


def test_execute_skips_auto_ingest_when_chromadb_has_evidence():
    """Quando ChromaDB ja tem chunks, nao busca PubMed."""
    chunks = [{"text": "evidence chunk"}]
    fake_report = {
        "report": {"summary": "Relatorio com RAG"},
        "tokens": {"input_tokens": 10},
        "model": "gemini",
        "rag_used": True,
    }

    agent = AgenteCientifico()
    search_mock = MagicMock(return_value={"chunks": chunks, "has_evidence": True})
    ingest_mock = MagicMock()
    report_mock = MagicMock(return_value=fake_report)

    patches = _patch_skills(
        agent,
        search_evidence=search_mock,
        auto_ingest_evidence=ingest_mock,
        generate_report=report_mock,
    )
    _enter_all(patches)
    try:
        result = agent.execute(treatment_plan=_make_treatment_plan())
    finally:
        _exit_all(patches)

    assert result.success is True
    assert result.data["chunks_used"] == 1
    assert result.data["rag_used"] is True
    ingest_mock.assert_not_called()
    assert search_mock.call_count == 1


def test_execute_triggers_auto_ingest_when_chromadb_empty():
    """Quando ChromaDB vazio, dispara auto_ingest_evidence e re-busca."""
    fake_report = {
        "report": {"summary": "Relatorio sem RAG"},
        "tokens": {},
        "model": "gpt-4o-mini",
        "rag_used": False,
    }

    agent = AgenteCientifico()

    search_mock = MagicMock(side_effect=[
        {"chunks": [], "has_evidence": False},
        {"chunks": [{"text": "novo chunk"}], "has_evidence": True},
    ])
    ingest_mock = MagicMock(return_value={"articles_seen": 3, "registered": 2, "chunks_added": 2})
    report_mock = MagicMock(return_value=fake_report)

    patches = _patch_skills(
        agent,
        search_evidence=search_mock,
        auto_ingest_evidence=ingest_mock,
        generate_report=report_mock,
    )
    _enter_all(patches)
    try:
        result = agent.execute(treatment_plan=_make_treatment_plan(), created_by=7)
    finally:
        _exit_all(patches)

    ingest_mock.assert_called_once()
    assert ingest_mock.call_args.kwargs["created_by"] == 7
    assert search_mock.call_count == 2
    assert result.data["auto_ingest"]["chunks_added"] == 2
    chunks_passed = report_mock.call_args.kwargs["chunks"]
    assert chunks_passed == [{"text": "novo chunk"}]


def test_execute_skips_auto_ingest_when_disabled_via_kwarg():
    """auto_ingest_evidence=False mantem o comportamento antigo (so fallback)."""
    fake_report = {
        "report": {"summary": "Sem RAG"},
        "tokens": {},
        "model": "gpt-4o-mini",
        "rag_used": False,
    }
    agent = AgenteCientifico()
    ingest_mock = MagicMock()

    patches = _patch_skills(
        agent,
        search_evidence=MagicMock(return_value={"chunks": [], "has_evidence": False}),
        auto_ingest_evidence=ingest_mock,
        generate_report=MagicMock(return_value=fake_report),
    )
    _enter_all(patches)
    try:
        result = agent.execute(treatment_plan=_make_treatment_plan(), auto_ingest_evidence=False)
    finally:
        _exit_all(patches)

    ingest_mock.assert_not_called()
    assert result.success is True
    assert "auto_ingest" not in result.data


def test_execute_continues_when_auto_ingest_finds_nothing():
    """Se PubMed nao retorna nada, segue para fallback non-RAG sem quebrar."""
    fake_report = {
        "report": {"summary": "Fallback"},
        "tokens": {},
        "model": "gpt-4o-mini",
        "rag_used": False,
    }
    agent = AgenteCientifico()
    search_mock = MagicMock(return_value={"chunks": [], "has_evidence": False})

    patches = _patch_skills(
        agent,
        search_evidence=search_mock,
        auto_ingest_evidence=MagicMock(return_value={"articles_seen": 0, "registered": 0, "chunks_added": 0}),
        generate_report=MagicMock(return_value=fake_report),
    )
    _enter_all(patches)
    try:
        result = agent.execute(treatment_plan=_make_treatment_plan())
    finally:
        _exit_all(patches)

    assert result.success is True
    assert search_mock.call_count == 1
    assert result.data["chunks_used"] == 0
    assert result.data["rag_used"] is False


# ── _auto_ingest_evidence (skill em si) ──


def _pubmed_articles_payload(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"articles": articles, "total_found": len(articles), "query": "test"}


def test_auto_ingest_skill_filters_by_quality_and_registers():
    """Artigo de qualidade ruim (sem abstract) e descartado antes do registro."""
    high_quality = {
        "pmid": "111",
        "title": "Cannabidiol for refractory epilepsy: a systematic review",
        "authors": ["Doe J"],
        "journal": "Lancet",
        "published_date": "2021-01-01",
        "doi": "10.1/good",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/111/",
    }
    low_quality = {
        "pmid": "222",
        "title": "Short",  # titulo curto
        "authors": [],
        "journal": "",
        "published_date": None,
        "doi": "",
        "source_url": "",
    }

    abstracts = {
        "111": {"pmid": "111", "abstract": "Background: " + ("evidence " * 30), "success": True},
        "222": {"pmid": "222", "abstract": "Short.", "success": True},
    }

    fake_embedder = MagicMock()
    fake_embedder.embed_document.return_value = [0.1] * 4
    fake_store = MagicMock()

    agent = AgenteCientifico()
    register_calls: List[Dict[str, Any]] = []

    def fake_register(doc_data, created_by=None):
        register_calls.append(doc_data)
        return {"registered": True, "catalog_id": 901, "reason": None}

    with patch("src.knowledge.pubmed.search_pubmed_articles",
               return_value=_pubmed_articles_payload([high_quality, low_quality])), \
         patch("src.knowledge.pubmed.fetch_pubmed_abstract",
               side_effect=lambda pmid: abstracts[pmid]), \
         patch("src.knowledge.embeddings.EmbeddingClient", return_value=fake_embedder), \
         patch("src.knowledge.vector_store.KnowledgeStore", return_value=fake_store), \
         patch.object(agent, "register_to_knowledge_base", side_effect=fake_register), \
         patch("time.sleep"):
        result = agent._auto_ingest_evidence(query_text="cbd epilepsy", max_results=2, created_by=5)

    assert result["articles_seen"] == 2
    assert result["registered"] == 1  # apenas o high_quality
    assert result["chunks_added"] == 1
    assert len(register_calls) == 1
    assert register_calls[0]["doi"] == "10.1/good"
    fake_store.add.assert_called_once()


def test_auto_ingest_skill_skips_chroma_on_duplicate():
    """Se o registro retorna duplicate_doi, nao tenta embedar/inserir no Chroma."""
    article = {
        "pmid": "333",
        "title": "Cannabidiol in fibromyalgia: long-term outcomes",
        "authors": ["Foo"],
        "journal": "Pain",
        "published_date": "2020-05-05",
        "doi": "10.1/dup",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/333/",
    }
    abstract = {"pmid": "333", "abstract": "Background: " + ("text " * 30), "success": True}

    fake_embedder = MagicMock()
    fake_store = MagicMock()

    agent = AgenteCientifico()

    with patch("src.knowledge.pubmed.search_pubmed_articles",
               return_value=_pubmed_articles_payload([article])), \
         patch("src.knowledge.pubmed.fetch_pubmed_abstract", return_value=abstract), \
         patch("src.knowledge.embeddings.EmbeddingClient", return_value=fake_embedder), \
         patch("src.knowledge.vector_store.KnowledgeStore", return_value=fake_store), \
         patch.object(agent, "register_to_knowledge_base",
                      return_value={"registered": False, "reason": "duplicate_doi", "catalog_id": None}), \
         patch("time.sleep"):
        result = agent._auto_ingest_evidence(query_text="cbd fibromyalgia", max_results=1)

    assert result["registered"] == 0
    assert result["chunks_added"] == 0
    fake_store.add.assert_not_called()
    fake_embedder.embed_document.assert_not_called()


def test_auto_ingest_skill_returns_zeros_when_pubmed_empty():
    """Sem artigos no PubMed, retorna estrutura zerada e nao toca embedder."""
    fake_embedder = MagicMock()
    fake_store = MagicMock()
    agent = AgenteCientifico()

    with patch("src.knowledge.pubmed.search_pubmed_articles",
               return_value=_pubmed_articles_payload([])), \
         patch("src.knowledge.embeddings.EmbeddingClient", return_value=fake_embedder), \
         patch("src.knowledge.vector_store.KnowledgeStore", return_value=fake_store):
        result = agent._auto_ingest_evidence(query_text="rare query", max_results=3)

    assert result == {"articles_seen": 0, "registered": 0, "chunks_added": 0}
    fake_embedder.embed_document.assert_not_called()
