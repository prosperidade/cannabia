from __future__ import annotations

import sys
from types import ModuleType

import pytest
from flask import Flask
from flask_login import LoginManager

from src.web.auth_identity import AppUser
from src.web.routes.regulatory import regulatory_bp


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
