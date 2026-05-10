"""Testes do hook register_to_knowledge_base() no BaseAgent (C6)."""

from __future__ import annotations

from unittest.mock import patch

from src.ai.agents.base import AgentResult, BaseAgent


class _DummyAgent(BaseAgent):
    agent_name = "dummy"
    description = "Agent fake para testar register_to_knowledge_base"

    def execute(self, **kwargs) -> AgentResult:
        return AgentResult(success=True)


def test_register_to_kb_sets_ingested_by_with_agent_suffix():
    """O wrapper deve marcar ingested_by como agent_<nome>_auto."""
    captured = {}

    def fake_register(payload):
        captured["payload"] = payload
        return {"registered": True, "catalog_id": 1, "reason": None}

    with patch("src.knowledge.auto_ingest.register_article_in_catalog", side_effect=fake_register):
        agent = _DummyAgent()
        result = agent.register_to_knowledge_base({"title": "Test", "doi": "10.1/x"})

    assert result["registered"] is True
    assert captured["payload"]["ingested_by"] == "agent_dummy_auto"


def test_register_to_kb_respects_explicit_ingested_by():
    """Quando o caller ja informa ingested_by, nao sobrescreve."""
    captured = {}

    def fake_register(payload):
        captured["payload"] = payload
        return {"registered": True, "catalog_id": 1, "reason": None}

    with patch("src.knowledge.auto_ingest.register_article_in_catalog", side_effect=fake_register):
        agent = _DummyAgent()
        agent.register_to_knowledge_base({"title": "T", "ingested_by": "explicit_caller"})

    assert captured["payload"]["ingested_by"] == "explicit_caller"


def test_register_to_kb_propagates_created_by():
    """created_by passado como kwarg vai para o payload."""
    captured = {}

    def fake_register(payload):
        captured["payload"] = payload
        return {"registered": True, "catalog_id": 1, "reason": None}

    with patch("src.knowledge.auto_ingest.register_article_in_catalog", side_effect=fake_register):
        agent = _DummyAgent()
        agent.register_to_knowledge_base({"title": "T"}, created_by=42)

    assert captured["payload"]["created_by"] == 42


def test_register_to_kb_is_fire_and_forget_on_exception():
    """Exception no helper compartilhado nao deve subir — fire-and-forget."""

    def boom(_payload):
        raise RuntimeError("import failure")

    with patch("src.knowledge.auto_ingest.register_article_in_catalog", side_effect=boom):
        agent = _DummyAgent()
        result = agent.register_to_knowledge_base({"title": "T"})

    assert result["registered"] is False
    assert result["reason"] == "exception"
    assert "import failure" in result["error"]


def test_register_to_kb_passes_dedup_response_through():
    """Resposta de dedup do helper chega como esta para o caller."""

    def fake_register(_payload):
        return {"registered": False, "reason": "duplicate_doi", "catalog_id": None}

    with patch("src.knowledge.auto_ingest.register_article_in_catalog", side_effect=fake_register):
        agent = _DummyAgent()
        result = agent.register_to_knowledge_base({"title": "T", "doi": "10.1/dup"})

    assert result == {"registered": False, "reason": "duplicate_doi", "catalog_id": None}
