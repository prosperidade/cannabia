"""Tests do blueprint knowledge.

Sem DB — db_cursor e mockado via monkeypatch. Cobertura:
  - Listagem do catalogo + stats (com agregacoes)
  - Criacao e execucao de monitores
  - DELETE de catalogo e monitor com regra de autoria
    (Admin global vs AdminClinica/Medico)
  - Roles permitidas/bloqueadas em GET/POST
"""

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


CSRF_TOKEN = "test-csrf-token"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _build_client(*, user_id: int, role: str):
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret-key")

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(uid: str):
        if uid == str(user_id):
            return AppUser(user_id=user_id, username=role.lower(), role=role)
        return None

    app.register_blueprint(knowledge_bp)

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["csrf_token"] = CSRF_TOKEN
    return client


@pytest.fixture
def admin_client():
    return _build_client(user_id=1, role="Admin")


@pytest.fixture
def medico_client():
    return _build_client(user_id=42, role="Medico")


@pytest.fixture
def adminclinica_client():
    return _build_client(user_id=7, role="AdminClinica")


@pytest.fixture
def recepcao_client():
    return _build_client(user_id=99, role="Recepcao")


def _auth_headers() -> dict[str, str]:
    return {"Content-Type": "application/json", "X-CSRF-Token": CSRF_TOKEN}


# ---------------------------------------------------------------------------
# Catalog list + stats
# ---------------------------------------------------------------------------

def test_list_catalog_returns_items_and_meta(admin_client, monkeypatch):
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
                        "created_by": 1,
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

    response = admin_client.get(
        "/api/v1/knowledge/catalog?page=1&page_size=10&doc_type=legislation"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["data"][0]["title"] == "Lei 11.343/2006"
    assert payload["meta"]["total"] == 1
    assert payload["meta"]["type_stats"]["legislation"] == 1
    assert payload["meta"]["storage_stats"]["google_files"] == 1


def test_knowledge_stats_returns_storage_counts(admin_client, monkeypatch):
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

    response = admin_client.get("/api/v1/knowledge/stats")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["total_documents"] == 3
    assert payload["chromadb_chunks"] == 8
    assert payload["google_files_count"] == 2
    assert payload["by_storage"][0]["storage_type"] == "google_files"


# ---------------------------------------------------------------------------
# Monitors — criacao + run
# ---------------------------------------------------------------------------

def test_create_monitor_inserts_with_created_by(admin_client, monkeypatch):
    class FakeConn:
        def __init__(self):
            self.committed = False

        def commit(self):
            self.committed = True

    captured_params: dict[str, tuple] = {}

    class FakeCursor:
        def __init__(self):
            self._fetchone = None

        def execute(self, sql, params=()):
            normalized = " ".join(sql.split())
            if normalized.startswith("INSERT INTO knowledge_monitors"):
                captured_params["insert"] = params
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

    monkeypatch.setattr("src.web.routes.knowledge.db_cursor", fake_db_cursor)

    response = admin_client.post(
        "/api/v1/knowledge/monitors",
        headers=_auth_headers(),
        json={"name": "ANVISA", "url": "https://www.gov.br/anvisa"},
    )

    assert response.status_code == 201
    assert response.get_json()["data"]["id"] == 14
    assert fake_conn.committed is True
    # ultimo param da insercao deve ser o id do user logado (Admin = 1)
    assert captured_params["insert"][-1] == 1


def test_run_monitors_passes_created_by(admin_client, monkeypatch):
    captured: dict[str, object] = {}

    extractor_module = ModuleType("src.ai.agents.extrator")

    class FakeExtractor:
        def run(self, action, **kwargs):
            captured["action"] = action
            captured["kwargs"] = kwargs
            return SimpleNamespace(data={"processed": 2, "registered": 1})

    extractor_module.AgenteExtrator = FakeExtractor
    sys.modules["src.ai.agents.extrator"] = extractor_module

    response = admin_client.post(
        "/api/v1/knowledge/monitors/run",
        headers=_auth_headers(),
        json={},
    )

    assert response.status_code == 200
    assert captured["action"] == "run_monitors"
    assert captured["kwargs"]["created_by"] == 1


# ---------------------------------------------------------------------------
# DELETE catalog — regra de autoria
# ---------------------------------------------------------------------------

def _delete_cursor_factory(stored_created_by: int | None, *, found: bool = True):
    """Helper: gera FakeConn/FakeCursor que respondem ao SELECT created_by + DELETE."""

    class FakeConn:
        committed = False

        def commit(self):
            type(self).committed = True

    class FakeCursor:
        def __init__(self):
            self._fetchone = None

        def execute(self, sql, params=()):
            normalized = " ".join(sql.split())
            if normalized.startswith("SELECT id, created_by FROM knowledge_catalog WHERE id"):
                self._fetchone = (
                    {"id": params[0], "created_by": stored_created_by}
                    if found
                    else None
                )
            elif normalized.startswith("SELECT id, created_by FROM knowledge_monitors WHERE id"):
                self._fetchone = (
                    {"id": params[0], "created_by": stored_created_by}
                    if found
                    else None
                )
            elif normalized.startswith("DELETE FROM knowledge_catalog"):
                self._fetchone = None
            elif normalized.startswith("DELETE FROM knowledge_monitors"):
                self._fetchone = None
            else:
                raise AssertionError(f"Unexpected SQL: {normalized}")

        def fetchone(self):
            return self._fetchone

    return FakeConn, FakeCursor


def test_admin_can_delete_any_catalog_item(admin_client, monkeypatch):
    """Admin global deleta independente de quem adicionou."""
    FakeConn, FakeCursor = _delete_cursor_factory(stored_created_by=999)

    @contextmanager
    def fake_db_cursor(dictionary=False):
        yield FakeConn(), FakeCursor()

    monkeypatch.setattr("src.web.routes.knowledge.db_cursor", fake_db_cursor)

    resp = admin_client.delete(
        "/api/v1/knowledge/catalog/42",
        headers=_auth_headers(),
        json={},
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"] == {"deleted": True, "id": 42}


def test_adminclinica_can_delete_own_catalog_item(adminclinica_client, monkeypatch):
    """AdminClinica deleta o que ela mesma adicionou (created_by == user_id=7)."""
    FakeConn, FakeCursor = _delete_cursor_factory(stored_created_by=7)

    @contextmanager
    def fake_db_cursor(dictionary=False):
        yield FakeConn(), FakeCursor()

    monkeypatch.setattr("src.web.routes.knowledge.db_cursor", fake_db_cursor)

    resp = adminclinica_client.delete(
        "/api/v1/knowledge/catalog/42",
        headers=_auth_headers(),
        json={},
    )
    assert resp.status_code == 200


def test_adminclinica_cannot_delete_others_catalog_item(adminclinica_client, monkeypatch):
    """AdminClinica NAO pode deletar item criado por outro usuario."""
    FakeConn, FakeCursor = _delete_cursor_factory(stored_created_by=999)

    @contextmanager
    def fake_db_cursor(dictionary=False):
        yield FakeConn(), FakeCursor()

    monkeypatch.setattr("src.web.routes.knowledge.db_cursor", fake_db_cursor)

    resp = adminclinica_client.delete(
        "/api/v1/knowledge/catalog/42",
        headers=_auth_headers(),
        json={},
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "forbidden"


def test_medico_cannot_delete_others_catalog_item(medico_client, monkeypatch):
    """Medico nao-dono nao pode deletar item criado por outro usuario."""
    FakeConn, FakeCursor = _delete_cursor_factory(stored_created_by=999)

    @contextmanager
    def fake_db_cursor(dictionary=False):
        yield FakeConn(), FakeCursor()

    monkeypatch.setattr("src.web.routes.knowledge.db_cursor", fake_db_cursor)

    resp = medico_client.delete(
        "/api/v1/knowledge/catalog/42",
        headers=_auth_headers(),
        json={},
    )
    assert resp.status_code == 403


def test_medico_can_delete_own_catalog_item(medico_client, monkeypatch):
    """Medico deleta o que ele mesmo adicionou (user_id=42)."""
    FakeConn, FakeCursor = _delete_cursor_factory(stored_created_by=42)

    @contextmanager
    def fake_db_cursor(dictionary=False):
        yield FakeConn(), FakeCursor()

    monkeypatch.setattr("src.web.routes.knowledge.db_cursor", fake_db_cursor)

    resp = medico_client.delete(
        "/api/v1/knowledge/catalog/42",
        headers=_auth_headers(),
        json={},
    )
    assert resp.status_code == 200


def test_delete_catalog_404_when_missing(admin_client, monkeypatch):
    FakeConn, FakeCursor = _delete_cursor_factory(stored_created_by=None, found=False)

    @contextmanager
    def fake_db_cursor(dictionary=False):
        yield FakeConn(), FakeCursor()

    monkeypatch.setattr("src.web.routes.knowledge.db_cursor", fake_db_cursor)

    resp = admin_client.delete(
        "/api/v1/knowledge/catalog/9999",
        headers=_auth_headers(),
        json={},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE monitor — mesma regra
# ---------------------------------------------------------------------------

def test_admin_can_delete_any_monitor(admin_client, monkeypatch):
    FakeConn, FakeCursor = _delete_cursor_factory(stored_created_by=999)

    @contextmanager
    def fake_db_cursor(dictionary=False):
        yield FakeConn(), FakeCursor()

    monkeypatch.setattr("src.web.routes.knowledge.db_cursor", fake_db_cursor)

    resp = admin_client.delete(
        "/api/v1/knowledge/monitors/14",
        headers=_auth_headers(),
        json={},
    )
    assert resp.status_code == 200


def test_adminclinica_cannot_delete_others_monitor(adminclinica_client, monkeypatch):
    FakeConn, FakeCursor = _delete_cursor_factory(stored_created_by=999)

    @contextmanager
    def fake_db_cursor(dictionary=False):
        yield FakeConn(), FakeCursor()

    monkeypatch.setattr("src.web.routes.knowledge.db_cursor", fake_db_cursor)

    resp = adminclinica_client.delete(
        "/api/v1/knowledge/monitors/14",
        headers=_auth_headers(),
        json={},
    )
    assert resp.status_code == 403


def test_medico_cannot_delete_monitor(medico_client, monkeypatch):
    """Medico nao tem permissao para mexer em monitors (so Admin/AdminClinica)."""
    resp = medico_client.delete(
        "/api/v1/knowledge/monitors/14",
        headers=_auth_headers(),
        json={},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Roles bloqueadas — Recepcao nao acessa nada
# ---------------------------------------------------------------------------

def test_recepcao_blocked_from_catalog(recepcao_client, monkeypatch):
    """Recepcao nao acessa a base cientifica (decisao do produto)."""
    monkeypatch.setattr("src.web.routes.knowledge.db_cursor", lambda **_: None)

    resp = recepcao_client.get("/api/v1/knowledge/catalog")
    assert resp.status_code == 403


def test_recepcao_blocked_from_stats(recepcao_client):
    resp = recepcao_client.get("/api/v1/knowledge/stats")
    assert resp.status_code == 403


def test_recepcao_blocked_from_auto_search(recepcao_client):
    resp = recepcao_client.post(
        "/api/v1/knowledge/auto-search",
        headers=_auth_headers(),
        json={},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Roles permitidas — leitura
# ---------------------------------------------------------------------------

def test_adminclinica_can_read_catalog(adminclinica_client, monkeypatch):
    """AdminClinica pode ler o catalogo (acesso ampliado em P1)."""

    class FakeCursor:
        def __init__(self):
            self._fetchall = []

        def execute(self, sql, params=()):
            normalized = " ".join(sql.split())
            if "FROM knowledge_catalog" in normalized:
                self._fetchall = []
            else:
                raise AssertionError(f"Unexpected SQL: {normalized}")

        def fetchall(self):
            return self._fetchall

    @contextmanager
    def fake_db_cursor(dictionary=False):
        yield object(), FakeCursor()

    monkeypatch.setattr("src.web.routes.knowledge.db_cursor", fake_db_cursor)

    resp = adminclinica_client.get("/api/v1/knowledge/catalog")
    assert resp.status_code == 200


def test_medico_can_read_catalog(medico_client, monkeypatch):
    class FakeCursor:
        def __init__(self):
            self._fetchall = []

        def execute(self, sql, params=()):
            self._fetchall = []

        def fetchall(self):
            return self._fetchall

    @contextmanager
    def fake_db_cursor(dictionary=False):
        yield object(), FakeCursor()

    monkeypatch.setattr("src.web.routes.knowledge.db_cursor", fake_db_cursor)

    resp = medico_client.get("/api/v1/knowledge/catalog")
    assert resp.status_code == 200
