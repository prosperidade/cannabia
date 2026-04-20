from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace

import pytest
from flask import Flask
from flask_login import LoginManager

from src.web.auth_identity import AppUser
from src.web.routes.knowledge import knowledge_bp


@pytest.fixture
def knowledge_client():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
    )

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == "1":
            return AppUser(user_id=1, username="admin", role="Admin")
        return None

    app.register_blueprint(knowledge_bp)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = "1"
            session["csrf_token"] = "test-csrf-token"
        yield client


def test_list_catalog_returns_items_and_meta(knowledge_client, monkeypatch):
    class FakeCursor:
        def __init__(self):
            self._fetchall = []

        def execute(self, sql, params=()):
            normalized = " ".join(sql.split())
            if "FROM knowledge_catalog" in normalized and "ORDER BY created_at DESC" in normalized:
                self._fetchall = [
                    {
                        "id": 2,
                        "title": "Lei 11.343/2006",
                        "doc_type": "legislation",
                        "source": "planalto",
                        "source_url": None,
                        "doi": None,
                        "category": "cannabis_medicinal",
                        "tags": ["legislation"],
                        "authors": [],
                        "journal": None,
                        "published_date": None,
                        "norm_number": "Lei 11.343/2006",
                        "norm_body": "Congresso Nacional",
                        "norm_status": None,
                        "storage_type": "google_files",
                        "chromadb_chunks": 0,
                        "google_file_uri": "gs://lei11343",
                        "status": "indexed",
                        "ingested_by": "manual_upload",
                        "ingested_at": datetime(2026, 4, 15, tzinfo=timezone.utc),
                        "created_at": datetime(2026, 4, 15, tzinfo=timezone.utc),
                    }
                ]
            elif normalized.startswith("SELECT doc_type, COUNT(*) AS cnt FROM knowledge_catalog GROUP BY doc_type"):
                self._fetchall = [{"doc_type": "legislation", "cnt": 1}]
            elif normalized.startswith("SELECT storage_type, COUNT(*) AS cnt FROM knowledge_catalog GROUP BY storage_type"):
                self._fetchall = [{"storage_type": "google_files", "cnt": 1}]
            else:
                raise AssertionError(f"Unexpected SQL: {normalized}")

        def fetchall(self):
            return self._fetchall

    @contextmanager
    def fake_db_cursor(dictionary=False):
        assert dictionary is True
        yield object(), FakeCursor()

    monkeypatch.setattr("src.web.routes.knowledge.db_cursor", fake_db_cursor)

    response = knowledge_client.get("/api/v1/knowledge/catalog?page=1&page_size=10&doc_type=legislation")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["data"][0]["title"] == "Lei 11.343/2006"
    assert payload["meta"]["total"] == 1
    assert payload["meta"]["type_stats"]["legislation"] == 1
    assert payload["meta"]["storage_stats"]["google_files"] == 1


def test_knowledge_stats_returns_storage_counts(knowledge_client, monkeypatch):
    class FakeCursor:
        def __init__(self):
            self._fetchone = None
            self._fetchall = []

        def execute(self, sql, params=()):
            normalized = " ".join(sql.split())
            if normalized.startswith("SELECT COUNT(*) AS total FROM knowledge_catalog"):
                self._fetchone = {"total": 3}
            elif normalized.startswith("SELECT doc_type, COUNT(*) AS cnt FROM knowledge_catalog GROUP BY doc_type ORDER BY cnt DESC"):
                self._fetchall = [{"doc_type": "legislation", "cnt": 2}, {"doc_type": "article", "cnt": 1}]
            elif normalized.startswith("SELECT source, COUNT(*) AS cnt FROM knowledge_catalog GROUP BY source ORDER BY cnt DESC"):
                self._fetchall = [{"source": "anvisa", "cnt": 2}]
            elif normalized.startswith("SELECT storage_type, COUNT(*) AS cnt FROM knowledge_catalog GROUP BY storage_type ORDER BY cnt DESC"):
                self._fetchall = [{"storage_type": "google_files", "cnt": 2}, {"storage_type": "chromadb", "cnt": 1}]
            elif normalized.startswith("SELECT status, COUNT(*) AS cnt FROM knowledge_catalog GROUP BY status ORDER BY cnt DESC"):
                self._fetchall = [{"status": "indexed", "cnt": 3}]
            else:
                raise AssertionError(f"Unexpected SQL: {normalized}")

        def fetchone(self):
            return self._fetchone

        def fetchall(self):
            return self._fetchall

    @contextmanager
    def fake_db_cursor(dictionary=False):
        assert dictionary is True
        yield object(), FakeCursor()

    vector_store_module = ModuleType("src.knowledge.vector_store")
    vector_store_module.KnowledgeStore = lambda: SimpleNamespace(count=lambda: 8)
    google_files_module = ModuleType("src.knowledge.google_files")
    google_files_module.list_uploaded_files = lambda: [{"name": "rdc-327"}, {"name": "lei-11343"}]
    sys.modules["src.knowledge.vector_store"] = vector_store_module
    sys.modules["src.knowledge.google_files"] = google_files_module

    monkeypatch.setattr("src.web.routes.knowledge.db_cursor", fake_db_cursor)

    response = knowledge_client.get("/api/v1/knowledge/stats")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["total_documents"] == 3
    assert payload["chromadb_chunks"] == 8
    assert payload["google_files_count"] == 2
    assert payload["by_storage"][0]["storage_type"] == "google_files"


def test_create_monitor_and_run_monitors(knowledge_client, monkeypatch):
    class FakeConn:
        def __init__(self):
            self.committed = False

        def commit(self):
            self.committed = True

    class FakeCursor:
        def __init__(self):
            self._fetchone = None

        def execute(self, sql, params=()):
            normalized = " ".join(sql.split())
            if normalized.startswith("INSERT INTO knowledge_monitors"):
                self._fetchone = {"id": 14, "created_at": datetime(2026, 4, 16, tzinfo=timezone.utc)}
            else:
                raise AssertionError(f"Unexpected SQL: {normalized}")

        def fetchone(self):
            return self._fetchone

    fake_conn = FakeConn()

    @contextmanager
    def fake_db_cursor(dictionary=False):
        assert dictionary is True
        yield fake_conn, FakeCursor()

    extractor_module = ModuleType("src.ai.agents.extrator")

    class FakeExtractor:
        def run(self, action, **kwargs):
            assert action == "run_monitors"
            return SimpleNamespace(data={"processed": 2, "registered": 1})

    extractor_module.AgenteExtrator = FakeExtractor
    sys.modules["src.ai.agents.extrator"] = extractor_module

    monkeypatch.setattr("src.web.routes.knowledge.db_cursor", fake_db_cursor)

    create_response = knowledge_client.post(
        "/api/v1/knowledge/monitors",
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": "test-csrf-token",
        },
        json={"name": "ANVISA", "url": "https://www.gov.br/anvisa"},
    )

    run_response = knowledge_client.post(
        "/api/v1/knowledge/monitors/run",
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": "test-csrf-token",
        },
        json={},
    )

    assert create_response.status_code == 201
    assert create_response.get_json()["data"]["id"] == 14
    assert fake_conn.committed is True
    assert run_response.status_code == 200
    assert run_response.get_json()["data"]["processed"] == 2
