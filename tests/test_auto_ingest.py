"""Testes do helper compartilhado de ingestao na knowledge_catalog (C6)."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from src.knowledge.auto_ingest import (
    is_quality_acceptable,
    register_article_in_catalog,
)


@contextmanager
def _fake_db_cursor(*, fetchone_results=None):
    """Helper: simula db_cursor(dictionary=True) yielding (conn, cursor)."""
    conn = MagicMock(name="conn")
    cursor = MagicMock(name="cursor")
    cursor.fetchone.side_effect = list(fetchone_results or [])
    yield conn, cursor


# ── register_article_in_catalog ──


def test_register_inserts_when_not_duplicate():
    """INSERT acontece quando nem DOI nem URL existem."""
    fetchone_results = [None, None, {"id": 123}]

    def fake_db_cursor(dictionary=True):
        return _fake_db_cursor(fetchone_results=fetchone_results)

    with patch("src.infra.database.db_cursor", side_effect=fake_db_cursor):
        result = register_article_in_catalog(
            {
                "title": "Test article",
                "doi": "10.1234/abc",
                "source_url": "https://pubmed.ncbi.nlm.nih.gov/999/",
                "abstract": "Estudo controlado randomizado sobre canabidiol em epilepsia refrataria.",
                "authors": ["Doe J"],
                "tags": ["cbd"],
            }
        )

    assert result == {"registered": True, "catalog_id": 123, "reason": None}


def test_register_returns_duplicate_doi_without_inserting():
    """Quando o DOI ja existe, nao tenta inserir."""
    cursor = MagicMock()
    cursor.fetchone.return_value = {"id": 7}
    conn = MagicMock()

    @contextmanager
    def fake_db_cursor(dictionary=True):
        yield conn, cursor

    with patch("src.infra.database.db_cursor", fake_db_cursor):
        result = register_article_in_catalog({"doi": "10.1234/dup", "title": "X"})

    assert result["registered"] is False
    assert result["reason"] == "duplicate_doi"
    # Apenas o SELECT por DOI ocorreu — sem INSERT.
    assert cursor.execute.call_count == 1


def test_register_returns_duplicate_url_when_no_doi():
    """Quando nao ha DOI, dedup cai no source_url."""
    fetchone_results = [{"id": 11}]  # SELECT por url
    cursor = MagicMock()
    cursor.fetchone.side_effect = fetchone_results
    conn = MagicMock()

    @contextmanager
    def fake_db_cursor(dictionary=True):
        yield conn, cursor

    with patch("src.infra.database.db_cursor", fake_db_cursor):
        result = register_article_in_catalog(
            {"source_url": "https://example.com/dup", "title": "X"}
        )

    assert result["registered"] is False
    assert result["reason"] == "duplicate_url"


def test_register_returns_db_error_on_exception():
    """Excecoes do DB nao sobem — viram db_error."""

    def raises(*_args, **_kwargs):
        raise RuntimeError("connection refused")

    with patch("src.infra.database.db_cursor", side_effect=raises):
        result = register_article_in_catalog({"title": "X"})

    assert result["registered"] is False
    assert result["reason"] == "db_error"
    assert "connection refused" in result["error"]


# ── is_quality_acceptable (politica leve de curadoria) ──


def _good_article():
    return {
        "title": "Cannabidiol for chronic pain: systematic review",
        "abstract": "Background: this systematic review evaluated the efficacy of CBD in chronic pain across 12 RCTs.",
        "doi": "10.1234/abc",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/999/",
    }


def test_quality_accepts_complete_article():
    assert is_quality_acceptable(_good_article()) is True


def test_quality_rejects_short_title():
    article = {**_good_article(), "title": "CBD"}
    assert is_quality_acceptable(article) is False


def test_quality_rejects_short_abstract():
    article = {**_good_article(), "abstract": "Short."}
    assert is_quality_acceptable(article) is False


def test_quality_rejects_when_no_doi_and_no_url():
    article = {**_good_article(), "doi": "", "source_url": ""}
    assert is_quality_acceptable(article) is False


def test_quality_accepts_when_only_url_present():
    article = {**_good_article(), "doi": ""}
    assert is_quality_acceptable(article) is True
