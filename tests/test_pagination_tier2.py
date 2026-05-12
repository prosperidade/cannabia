"""Tests da Sprint 3 Track Page-Migration — Tier-2 + dividas Sprint 2.

Cobre:
  - Envelope `Paginated<T>` em 4 endpoints Tier-2 (governance docs/rts,
    medical-record entries, patient timeline cursor-based).
  - Compat path (`limit=None` -> list[dict]).
  - `limit > MAX_LIMIT` -> HTTP 400 `invalid_limit`.
  - `?legacy=1` -> headers `Deprecation` + `Sunset` + logger.warning.
  - Cursor-based `before_id` em patient_timeline.
"""

from __future__ import annotations

from typing import Any

import pytest
from flask import Flask, g
from flask_login import LoginManager

from src.web.auth_identity import AppUser
from src.web.routes.api_v1 import api_v1_bp
from src.web.routes.governance import governance_bp


TENANT_ID = 42
CLINIC_ID = 42
ADMIN_ID = 10
CSRF_TOKEN = "test-csrf-token"


@pytest.fixture
def app_client():
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == str(ADMIN_ID):
            return AppUser(user_id=ADMIN_ID, username="admin", role="Admin")
        return None

    @app.before_request
    def inject_context():
        g.tenant_id = TENANT_ID
        g.clinic_id = CLINIC_ID

    app.register_blueprint(governance_bp)
    app.register_blueprint(api_v1_bp)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = str(ADMIN_ID)
            session["csrf_token"] = CSRF_TOKEN
        yield client


# ---------------------------------------------------------------------------
# Tier-2 #1: governance documents — envelope + compat
# ---------------------------------------------------------------------------

class TestGovernanceDocumentsTier2:
    def test_default_returns_compat_list(self, app_client, monkeypatch):
        """Sem `?paginated=1` -> shape Sprint 1 (compat path)."""
        captured: dict[str, Any] = {}

        def fake_list(**kwargs):
            captured.update(kwargs)
            return [{"id": 1, "document_type": "statute"}]

        monkeypatch.setattr(
            "src.web.routes.governance.repo.list_institutional_documents",
            fake_list,
        )
        response = app_client.get("/api/v1/governance/documents")
        assert response.status_code == 200
        # Compat path: documents e lista nua.
        data = response.get_json()["data"]["documents"]
        assert isinstance(data, list)
        # Sem limit -> caller nao deve passar kwargs de paginacao.
        assert "limit" not in captured

    def test_paginated_returns_envelope(self, app_client, monkeypatch):
        """`?paginated=1&limit=10` -> envelope canonico."""
        monkeypatch.setattr(
            "src.web.routes.governance.repo.list_institutional_documents",
            lambda **kwargs: {
                "items": [{"id": i} for i in range(1, 4)],
                "total": None,
                "has_more": False,
            },
        )
        response = app_client.get(
            "/api/v1/governance/documents?paginated=1&limit=10"
        )
        assert response.status_code == 200
        env = response.get_json()["data"]["documents"]
        assert set(env.keys()) == {"items", "total", "limit", "offset", "has_more"}
        assert env["limit"] == 10
        assert env["offset"] == 0
        assert env["has_more"] is False
        assert len(env["items"]) == 3


# ---------------------------------------------------------------------------
# Tier-2 #2: governance RTs (technical_responsibles)
# ---------------------------------------------------------------------------

class TestGovernanceRtsTier2:
    def test_paginated_envelope(self, app_client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.governance.repo.list_technical_responsibles",
            lambda **kwargs: {
                "items": [{"id": 1, "full_name": "Dr. X"}],
                "total": 1,
                "has_more": False,
            },
        )
        response = app_client.get(
            "/api/v1/governance/rts?paginated=1&limit=50&include_total=1"
        )
        assert response.status_code == 200
        env = response.get_json()["data"]["technical_responsibles"]
        assert env["items"][0]["full_name"] == "Dr. X"
        assert env["limit"] == 50


# ---------------------------------------------------------------------------
# Tier-2 #3: medical record entries — compat path + envelope
# ---------------------------------------------------------------------------

class TestMedicalRecordEntriesTier2:
    def test_default_returns_compat_entries_list(self, app_client, monkeypatch):
        """Caller interno (atendimentos.py) precisa `entries` como list."""
        monkeypatch.setattr(
            "src.web.routes.api_v1.get_medical_record_by_patient",
            lambda _c, _p: {"id": 1, "patient_id": 7},
        )
        monkeypatch.setattr(
            "src.web.routes.api_v1.list_patient_record_entries",
            lambda _c, _p, limit=50: [{"id": 1, "title": "Consulta"}],
        )
        response = app_client.get("/api/v1/patients/7/medical-record")
        assert response.status_code == 200
        data = response.get_json()["data"]
        assert isinstance(data["entries"], list)
        assert data["entries"][0]["id"] == 1

    def test_paginated_returns_envelope(self, app_client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.api_v1.get_medical_record_by_patient",
            lambda _c, _p: {"id": 1, "patient_id": 7},
        )

        def fake_entries(_c, _p, limit=None, offset=0, include_total=False, paginated=False):
            assert paginated is True
            assert limit == 5
            return {
                "items": [{"id": i, "title": f"E{i}"} for i in range(1, 6)],
                "total": None,
                "has_more": True,
            }

        monkeypatch.setattr(
            "src.web.routes.api_v1.list_patient_record_entries", fake_entries
        )
        response = app_client.get(
            "/api/v1/patients/7/medical-record?paginated=1&limit=5"
        )
        assert response.status_code == 200
        env = response.get_json()["data"]["entries"]
        assert env["items"][0]["title"] == "E1"
        assert env["has_more"] is True
        assert env["limit"] == 5


# ---------------------------------------------------------------------------
# Tier-2 #4: patient timeline — CURSOR-BASED (before_id)
# ---------------------------------------------------------------------------

class TestPatientTimelineCursorTier2:
    def test_default_returns_compat_list(self, app_client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.api_v1.list_patient_events",
            lambda _c, _p, limit=20: [
                {"id": 3, "title": "evt3"},
                {"id": 2, "title": "evt2"},
                {"id": 1, "title": "evt1"},
            ],
        )
        response = app_client.get("/api/v1/patients/7/timeline")
        assert response.status_code == 200
        data = response.get_json()["data"]
        assert isinstance(data, list)
        assert data[0]["title"] == "evt3"

    def test_cursor_paginated_envelope(self, app_client, monkeypatch):
        """`?before_id=N` -> envelope cursor-based com `next_cursor`."""
        captured: dict[str, Any] = {}

        def fake_list(_c, _p, limit=20, before_id=None, paginated=False):
            captured["before_id"] = before_id
            captured["paginated"] = paginated
            return {
                "items": [
                    {"id": 5, "title": "e5"},
                    {"id": 4, "title": "e4"},
                ],
                "has_more": True,
                "next_cursor": 4,
            }

        monkeypatch.setattr(
            "src.web.routes.api_v1.list_patient_events", fake_list
        )
        response = app_client.get(
            "/api/v1/patients/7/timeline?before_id=10&limit=2"
        )
        assert response.status_code == 200
        env = response.get_json()["data"]
        assert env["items"][0]["id"] == 5
        assert env["has_more"] is True
        assert env["next_cursor"] == 4
        assert env["limit"] == 2
        # E o repo recebeu cursor correto.
        assert captured["before_id"] == 10
        assert captured["paginated"] is True

    def test_invalid_before_id_returns_422(self, app_client):
        response = app_client.get("/api/v1/patients/7/timeline?before_id=abc")
        assert response.status_code == 422
        assert response.get_json()["error"]["code"] == "validation_error"


# ---------------------------------------------------------------------------
# Sprint 3 cross-cutting: invalid_limit + deprecation headers
# ---------------------------------------------------------------------------

class TestPaginationCrossCutting:
    def test_limit_above_max_returns_400_invalid_limit(
        self, app_client, monkeypatch
    ):
        """`limit > MAX_LIMIT (200)` -> HTTP 400 com codigo `invalid_limit`.

        Era clamp silencioso na Sprint 2; Sprint 3 explicita o erro pra
        permitir retry inteligente no frontend.
        """
        # Stub do repo: nao deve ser chamado (parse_pagination falha antes).
        monkeypatch.setattr(
            "src.web.routes.api_v1.list_reports",
            lambda *a, **k: pytest.fail("repo nao deveria ser chamado"),
        )
        response = app_client.get("/api/v1/attendances?limit=5000")
        assert response.status_code == 400
        body = response.get_json()
        assert body["error"]["code"] == "invalid_limit"
        assert "200" in body["error"]["message"]

    def test_legacy_mode_emits_deprecation_headers(
        self, app_client, monkeypatch
    ):
        """`?legacy=1` -> headers `Deprecation: true` + `Sunset: 2026-08-01`."""
        monkeypatch.setattr(
            "src.web.routes.api_v1.list_reports",
            lambda *a, **k: [{"id": 1, "patient_name": "X"}],
        )
        response = app_client.get("/api/v1/attendances?legacy=1")
        assert response.status_code == 200
        assert response.headers.get("Deprecation") == "true"
        sunset = response.headers.get("Sunset", "")
        assert "2026" in sunset and "Aug" in sunset

    def test_at_max_limit_is_accepted(self, app_client, monkeypatch):
        """`limit == MAX_LIMIT` deve passar (somente >MAX rejeita)."""
        monkeypatch.setattr(
            "src.web.routes.api_v1.list_reports",
            lambda *a, **k: {"items": [], "total": None, "has_more": False},
        )
        response = app_client.get("/api/v1/attendances?limit=200")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Repos com compat path: contrato direto (limit=None -> list, limit=int -> dict)
# ---------------------------------------------------------------------------

class TestRepoCompatContract:
    """Smoke do contrato `limit=None vs limit=int` (sem DB; valida assinatura)."""

    def test_governance_repo_compat_signature(self):
        from src.repositories import governance_repository as repo
        import inspect

        sig = inspect.signature(repo.list_institutional_documents)
        params = sig.parameters
        assert "limit" in params and params["limit"].default is None
        assert "offset" in params and params["offset"].default == 0
        assert "include_total" in params

        sig2 = inspect.signature(repo.list_technical_responsibles)
        assert "limit" in sig2.parameters
        assert sig2.parameters["limit"].default is None

    def test_evidence_repo_compat_signature(self):
        from src.repositories import evidence_repository as repo
        import inspect

        sig = inspect.signature(repo.list_treatment_plans_by_condition)
        assert "limit" in sig.parameters
        assert sig.parameters["limit"].default is None

    def test_medical_record_repo_compat_signature(self):
        from src.repositories import medical_record_repository as repo
        import inspect

        sig = inspect.signature(repo.list_patient_record_entries)
        params = sig.parameters
        # paginated=False (default) -> compat
        assert "paginated" in params
        assert params["paginated"].default is False
        assert "offset" in params

    def test_timeline_repo_compat_signature(self):
        from src.repositories import patient_timeline_repository as repo
        import inspect

        sig = inspect.signature(repo.list_patient_events)
        params = sig.parameters
        assert "before_id" in params
        assert params["before_id"].default is None
        assert "paginated" in params
        assert params["paginated"].default is False
