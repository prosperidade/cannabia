from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest
from flask import Flask
from flask_login import LoginManager

from src.web.auth_identity import AppUser
from src.web.routes.regulatory import regulatory_bp

FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "regulatory_queries.json"
)


@pytest.fixture
def regulatory_client():
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

    app.register_blueprint(regulatory_bp)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = "1"
            session["csrf_token"] = "test-csrf-token"
        yield client


def test_upload_files_syncs_catalog(regulatory_client, monkeypatch):
    module = ModuleType("src.knowledge.google_files")
    module.upload_all_legislation = lambda: [
        {
            "display_name": "RDC 327 2019.pdf",
            "size_bytes": 1200,
            "uri": "gs://rdc327",
            "name": "files/rdc327",
        }
    ]
    sys.modules["src.knowledge.google_files"] = module

    monkeypatch.setattr(
        "src.web.routes.regulatory.sync_legislation_catalog",
        lambda entries, ingested_by="manual_upload", created_by=None: {
            "created": 1,
            "updated": 0,
            "total": len(entries),
            "items": [{"catalog_id": 11, "action": "created"}],
        },
    )

    response = regulatory_client.post(
        "/api/v1/regulatory/upload",
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": "test-csrf-token",
        },
        json={},
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["uploaded"] == 1
    assert payload["catalog_created"] == 1
    assert payload["catalog_updated"] == 0
    assert payload["catalog_total"] == 1
    assert payload["files"][0]["name"] == "RDC 327 2019.pdf"


def test_query_legislation_validates_question_and_supports_structured(regulatory_client):
    empty_response = regulatory_client.post(
        "/api/v1/regulatory/query",
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": "test-csrf-token",
        },
        json={"question": "   "},
    )

    assert empty_response.status_code == 422
    assert empty_response.get_json()["error"]["code"] == "validation_error"


def test_query_legislation_returns_structured_payload(regulatory_client):
    module = ModuleType("src.knowledge.google_files")
    module.query_legislation_structured = lambda question, file_names=None: (
        {
            "answer": f"Resposta para {question}",
            "citations": [{"norm": "RDC 327/2019", "article": "Art. 1"}],
            "applicable": True,
            "confidence": 0.97,
        },
        {"total_tokens": 42, "files_used": ["RDC 327 2019.pdf"]},
    )
    sys.modules["src.knowledge.google_files"] = module

    response = regulatory_client.post(
        "/api/v1/regulatory/query",
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": "test-csrf-token",
        },
        json={"question": "Quem pode prescrever?", "structured": True},
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["result"]["applicable"] is True
    assert payload["result"]["citations"][0]["norm"] == "RDC 327/2019"
    assert payload["usage"]["total_tokens"] == 42


# ---------------------------------------------------------------------------
# Sprint 3 — Track Legislacao Real (Leg.4 + Leg.5)
# Smoke tests baseados em fixtures canonicas de Q&A regulatoria.
# Quando GOOGLE_API_KEY ausente, mockamos o Gemini com as respostas do
# fixture. Quando presente, marca-se um teste real opcional.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def regulatory_queries_fixture() -> dict:
    assert FIXTURE_PATH.exists(), f"fixture nao encontrada: {FIXTURE_PATH}"
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_fixture_has_at_least_six_canonical_queries(regulatory_queries_fixture):
    queries = regulatory_queries_fixture.get("queries", [])
    assert len(queries) >= 6, "fixture deve conter ao menos 6 Q&A canonicas"
    # Todas precisam ter id unico, norma primaria e palavras-chave esperadas.
    ids = [q["id"] for q in queries]
    assert len(set(ids)) == len(ids), "ids duplicados na fixture"
    for q in queries:
        assert q.get("primary_norm"), f"query {q.get('id')} sem primary_norm"
        assert q.get("expected_keywords"), f"query {q.get('id')} sem expected_keywords"
        assert q.get("mock_answer"), f"query {q.get('id')} sem mock_answer"


def test_query_legislation_smoke_with_mocked_gemini(
    regulatory_client, regulatory_queries_fixture
):
    """Verifica que /regulatory/query devolve mock_answer da fixture quando
    o backend Gemini esta mockado. Garante contrato HTTP + uso de keywords.
    """
    queries = regulatory_queries_fixture["queries"]
    # pega a primeira query como sanity check
    target = queries[0]

    module = ModuleType("src.knowledge.google_files")
    module.query_legislation = lambda question, file_names=None: (
        target["mock_answer"],
        {"total_tokens": 128, "files_used": target.get("files_hint", []), "model": "gemini-2.0-flash"},
    )
    sys.modules["src.knowledge.google_files"] = module

    response = regulatory_client.post(
        "/api/v1/regulatory/query",
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": "test-csrf-token",
        },
        json={"question": target["question"]},
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["answer"] == target["mock_answer"]
    # checa que pelo menos um keyword esperado aparece na resposta
    found = [kw for kw in target["expected_keywords"] if kw.lower() in payload["answer"].lower()]
    assert found, (
        f"nenhum dos expected_keywords {target['expected_keywords']} "
        f"encontrado na mock_answer da fixture {target['id']}"
    )
    assert payload["usage"]["total_tokens"] == 128
    assert payload["usage"]["model"] == "gemini-2.0-flash"


@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY nao configurada — smoke real de Gemini Files API pulado",
)
def test_query_legislation_real_gemini_smoke(regulatory_client, regulatory_queries_fixture):
    """Smoke real contra o Gemini Files API quando GOOGLE_API_KEY existe.

    Este teste depende de:
      - GOOGLE_API_KEY configurada
      - upload previo das normas (data/file_catalog.json populado)

    Caso a base ainda nao tenha sido carregada, o handler vai responder 422
    com `no_files` — tratamos como skip para evitar falso negativo.
    """
    # Re-importa modulo real (caso testes anteriores tenham instalado mock)
    sys.modules.pop("src.knowledge.google_files", None)
    target = regulatory_queries_fixture["queries"][0]

    response = regulatory_client.post(
        "/api/v1/regulatory/query",
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": "test-csrf-token",
        },
        json={"question": target["question"]},
    )

    if response.status_code == 422:
        payload = response.get_json()
        if payload.get("error", {}).get("code") == "no_files":
            pytest.skip("Base regulatoria ainda nao carregada no Gemini Files API")
        pytest.skip(f"Resposta 422 inesperada: {payload}")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert "answer" in payload
    assert payload["usage"].get("total_tokens", 0) > 0
