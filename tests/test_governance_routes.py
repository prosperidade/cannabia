"""Testes do blueprint governance (F1.5 parte 1).

Cobre CRUD de association/documents/rts/capacity e endpoints de
elegibilidade. O repositorio e o service sao mockados via
``monkeypatch`` — a camada de dados real ja e testada no smoke de
F1.3/F1.4.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest
from flask import Flask, g
from flask_login import LoginManager

from src.web.auth_identity import AppUser
from src.web.routes.governance import governance_bp


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------

TENANT_ID = 42
CSRF_TOKEN = "test-csrf-token"
ADMIN_ID = 10


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
    def inject_tenant():
        g.tenant_id = TENANT_ID

    app.register_blueprint(governance_bp)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = str(ADMIN_ID)
            session["csrf_token"] = CSRF_TOKEN
        yield client


@pytest.fixture
def no_tenant_client():
    """Variante sem ``g.tenant_id`` para testar o erro de contexto."""
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == str(ADMIN_ID):
            return AppUser(user_id=ADMIN_ID, username="admin", role="Admin")
        return None

    app.register_blueprint(governance_bp)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = str(ADMIN_ID)
            session["csrf_token"] = CSRF_TOKEN
        yield client


def _auth_headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-CSRF-Token": CSRF_TOKEN,
    }


# ---------------------------------------------------------------------
# Association
# ---------------------------------------------------------------------

class TestAssociationEndpoints:
    def test_get_association_returns_repo_data(self, app_client, monkeypatch):
        stub = {"tenant_id": TENANT_ID, "members_count": 10}
        monkeypatch.setattr(
            "src.web.routes.governance.repo.get_association",
            lambda tid: stub if tid == TENANT_ID else None,
        )
        response = app_client.get("/api/v1/governance/association")
        assert response.status_code == 200
        assert response.get_json()["data"]["association"] == stub

    def test_put_association_rejects_invalid_members(self, app_client):
        response = app_client.put(
            "/api/v1/governance/association",
            headers=_auth_headers(),
            json={"members_count": -1},
        )
        assert response.status_code == 422
        assert response.get_json()["error"]["code"] == "validation_error"

    def test_put_association_rejects_non_list_board(self, app_client):
        response = app_client.put(
            "/api/v1/governance/association",
            headers=_auth_headers(),
            json={"directive_board": {"not": "a list"}},
        )
        assert response.status_code == 422

    def test_put_association_rejects_statute_from_other_tenant(self, app_client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.governance.repo.get_institutional_document",
            lambda _doc_id: {"id": 1, "tenant_id": TENANT_ID + 1},
        )
        response = app_client.put(
            "/api/v1/governance/association",
            headers=_auth_headers(),
            json={"statute_document_id": 1},
        )
        assert response.status_code == 404
        assert response.get_json()["error"]["code"] == "not_found"

    def test_put_association_happy_path(self, app_client, monkeypatch):
        captured: dict[str, Any] = {}

        def fake_upsert(**kwargs):
            captured.update(kwargs)
            return {"tenant_id": kwargs["tenant_id"], "members_count": kwargs["members_count"]}

        monkeypatch.setattr("src.web.routes.governance.repo.upsert_association", fake_upsert)
        response = app_client.put(
            "/api/v1/governance/association",
            headers=_auth_headers(),
            json={
                "members_count": 25,
                "directive_board": [{"role": "president", "name": "X"}],
                "is_judicial_operation": True,
            },
        )
        assert response.status_code == 200
        assert captured["tenant_id"] == TENANT_ID
        assert captured["members_count"] == 25
        assert captured["is_judicial_operation"] is True


# ---------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------

class TestDocumentEndpoints:
    def test_list_documents_filters_by_type(self, app_client, monkeypatch):
        captured: dict[str, Any] = {}

        def fake_list(**kwargs):
            captured.update(kwargs)
            return [{"id": 1, "document_type": "statute"}]

        monkeypatch.setattr(
            "src.web.routes.governance.repo.list_institutional_documents", fake_list
        )
        response = app_client.get(
            "/api/v1/governance/documents?type=statute&active_only=false"
        )
        assert response.status_code == 200
        assert captured == {
            "tenant_id": TENANT_ID,
            "document_type": "statute",
            "active_only": False,
        }

    def test_create_document_requires_all_fields(self, app_client):
        response = app_client.post(
            "/api/v1/governance/documents",
            headers=_auth_headers(),
            json={"document_type": "statute"},
        )
        assert response.status_code == 422
        assert "Campos obrigatorios" in response.get_json()["error"]["message"]

    def test_create_document_rejects_invalid_hash(self, app_client):
        response = app_client.post(
            "/api/v1/governance/documents",
            headers=_auth_headers(),
            json={
                "document_type": "statute",
                "title": "E",
                "version": "1.0",
                "file_uri": "s3://x",
                "file_hash": "too-short",
                "valid_from": "2026-01-01",
            },
        )
        assert response.status_code == 422
        assert "SHA-256" in response.get_json()["error"]["message"]

    def test_create_document_happy_path(self, app_client, monkeypatch):
        captured: dict[str, Any] = {}

        def fake_create(**kwargs):
            captured.update(kwargs)
            return {"id": 99, **kwargs, "is_active": True}

        monkeypatch.setattr(
            "src.web.routes.governance.repo.create_institutional_document", fake_create
        )
        response = app_client.post(
            "/api/v1/governance/documents",
            headers=_auth_headers(),
            json={
                "document_type": "statute",
                "title": "Estatuto",
                "version": "1.0",
                "file_uri": "s3://bucket/est.pdf",
                "file_hash": "a" * 64,
                "valid_from": "2026-01-01",
                "valid_until": "2030-01-01",
            },
        )
        assert response.status_code == 201
        assert captured["valid_from"] == date(2026, 1, 1)
        assert captured["valid_until"] == date(2030, 1, 1)
        assert captured["tenant_id"] == TENANT_ID

    def test_delete_document_enforces_tenant_scope(self, app_client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.governance.repo.get_institutional_document",
            lambda doc_id: {"id": doc_id, "tenant_id": TENANT_ID + 1},
        )
        response = app_client.delete(
            "/api/v1/governance/documents/5", headers=_auth_headers()
        )
        assert response.status_code == 404

    def test_delete_document_happy_path(self, app_client, monkeypatch):
        deactivated: list[int] = []
        monkeypatch.setattr(
            "src.web.routes.governance.repo.get_institutional_document",
            lambda doc_id: {"id": doc_id, "tenant_id": TENANT_ID},
        )
        monkeypatch.setattr(
            "src.web.routes.governance.repo.deactivate_institutional_document",
            lambda doc_id: deactivated.append(doc_id),
        )
        response = app_client.delete(
            "/api/v1/governance/documents/5", headers=_auth_headers()
        )
        assert response.status_code == 200
        assert deactivated == [5]


# ---------------------------------------------------------------------
# Technical Responsibles
# ---------------------------------------------------------------------

class TestRtEndpoints:
    def test_create_rt_happy_path(self, app_client, monkeypatch):
        captured: dict[str, Any] = {}

        def fake_create(**kwargs):
            captured.update(kwargs)
            return {"id": 7, **kwargs, "is_active": True}

        monkeypatch.setattr(
            "src.web.routes.governance.repo.create_technical_responsible", fake_create
        )
        response = app_client.post(
            "/api/v1/governance/rts",
            headers=_auth_headers(),
            json={
                "full_name": "Dra Teste",
                "professional_council": "crm",
                "council_number": "123456",
                "council_state": "sp",
                "habilitation_valid_until": "2028-01-01",
                "document_ids": [1, 2],
            },
        )
        assert response.status_code == 201
        assert captured["professional_council"] == "CRM"
        assert captured["council_state"] == "SP"
        assert captured["document_ids"] == [1, 2]
        assert captured["habilitation_valid_until"] == date(2028, 1, 1)

    def test_create_rt_rejects_bad_state(self, app_client):
        response = app_client.post(
            "/api/v1/governance/rts",
            headers=_auth_headers(),
            json={
                "full_name": "X",
                "professional_council": "CRM",
                "council_number": "1",
                "council_state": "BRASIL",
            },
        )
        assert response.status_code == 422
        assert "council_state" in response.get_json()["error"]["message"]

    def test_create_rt_surfaces_unique_conflict(self, app_client, monkeypatch):
        from psycopg2 import IntegrityError

        def fake_create(**_kwargs):
            raise IntegrityError('duplicate key value violates unique constraint "uq_tr_council"')

        monkeypatch.setattr(
            "src.web.routes.governance.repo.create_technical_responsible", fake_create
        )
        response = app_client.post(
            "/api/v1/governance/rts",
            headers=_auth_headers(),
            json={
                "full_name": "X",
                "professional_council": "CRM",
                "council_number": "1",
                "council_state": "SP",
            },
        )
        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "conflict"

    def test_patch_rt_enforces_tenant_scope(self, app_client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.governance.repo.get_technical_responsible",
            lambda rt_id: {"id": rt_id, "tenant_id": TENANT_ID + 99},
        )
        response = app_client.patch(
            "/api/v1/governance/rts/1",
            headers=_auth_headers(),
            json={"is_active": False},
        )
        assert response.status_code == 404

    def test_patch_rt_updates_only_known_fields(self, app_client, monkeypatch):
        captured: dict[str, Any] = {}

        def fake_update(rt_id, **fields):
            captured["id"] = rt_id
            captured["fields"] = fields
            return {"id": rt_id, **fields}

        monkeypatch.setattr(
            "src.web.routes.governance.repo.get_technical_responsible",
            lambda rt_id: {"id": rt_id, "tenant_id": TENANT_ID},
        )
        monkeypatch.setattr(
            "src.web.routes.governance.repo.update_technical_responsible", fake_update
        )
        response = app_client.patch(
            "/api/v1/governance/rts/7",
            headers=_auth_headers(),
            json={
                "full_name": "Novo Nome",
                "unknown_field": "ignored",
                "habilitation_valid_until": "2029-06-30",
            },
        )
        assert response.status_code == 200
        assert captured["id"] == 7
        assert "unknown_field" not in captured["fields"]
        assert captured["fields"]["habilitation_valid_until"] == date(2029, 6, 30)

    def test_delete_rt_deactivates(self, app_client, monkeypatch):
        called: list[int] = []
        monkeypatch.setattr(
            "src.web.routes.governance.repo.get_technical_responsible",
            lambda rt_id: {"id": rt_id, "tenant_id": TENANT_ID},
        )
        monkeypatch.setattr(
            "src.web.routes.governance.repo.deactivate_technical_responsible",
            lambda rt_id: called.append(rt_id),
        )
        response = app_client.delete(
            "/api/v1/governance/rts/7", headers=_auth_headers()
        )
        assert response.status_code == 200
        assert called == [7]


# ---------------------------------------------------------------------
# Capacity
# ---------------------------------------------------------------------

class TestCapacityEndpoints:
    def test_create_capacity_requires_score_dicts(self, app_client):
        response = app_client.post(
            "/api/v1/governance/capacity",
            headers=_auth_headers(),
            json={"infrastructure_score": "not a dict"},
        )
        assert response.status_code == 422
        assert "Scores obrigatorios" in response.get_json()["error"]["message"]

    def test_create_capacity_rejects_out_of_range_readiness(self, app_client):
        response = app_client.post(
            "/api/v1/governance/capacity",
            headers=_auth_headers(),
            json={
                "infrastructure_score": {},
                "human_resources_score": {},
                "process_maturity_score": {},
                "proposed_scale": {},
                "overall_readiness": 120,
            },
        )
        assert response.status_code == 422

    def test_create_capacity_happy_path(self, app_client, monkeypatch):
        captured: dict[str, Any] = {}

        def fake_create(**kwargs):
            captured.update(kwargs)
            return {"id": 3, **kwargs}

        monkeypatch.setattr(
            "src.web.routes.governance.repo.create_capacity_assessment", fake_create
        )
        response = app_client.post(
            "/api/v1/governance/capacity",
            headers=_auth_headers(),
            json={
                "assessment_date": "2026-04-20",
                "infrastructure_score": {"s": 80},
                "human_resources_score": {"s": 70},
                "process_maturity_score": {"s": 75},
                "proposed_scale": {"p": 50},
                "overall_readiness": 74.5,
            },
        )
        assert response.status_code == 201
        assert captured["overall_readiness"] == 74.5
        assert captured["tenant_id"] == TENANT_ID


# ---------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------

def _fake_report(is_eligible: bool = True):
    from src.services.governance_service import EligibilityFinding, EligibilityReport

    findings = [
        EligibilityFinding(code="legal_nature", status="pass" if is_eligible else "fail",
                           message="ok" if is_eligible else "no", details={}),
        EligibilityFinding(code="incorporation_time", status="pass", message="ok", details={}),
    ]
    return EligibilityReport(
        tenant_id=TENANT_ID,
        checked_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
        findings=findings,
    )


class TestEligibilityEndpoints:
    def test_get_eligibility_returns_report(self, app_client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.governance.check_sandbox_eligibility",
            lambda tid: _fake_report(True),
        )
        response = app_client.get("/api/v1/governance/eligibility")
        assert response.status_code == 200
        payload = response.get_json()["data"]
        assert payload["is_eligible"] is True
        assert payload["tenant_id"] == TENANT_ID
        assert len(payload["findings"]) == 2

    def test_get_eligibility_returns_404_when_tenant_missing(self, app_client, monkeypatch):
        def raise_value(_tid):
            raise ValueError("Tenant 42 nao encontrado.")

        monkeypatch.setattr(
            "src.web.routes.governance.check_sandbox_eligibility", raise_value
        )
        response = app_client.get("/api/v1/governance/eligibility")
        assert response.status_code == 404
        assert response.get_json()["error"]["code"] == "not_found"

    def test_refresh_eligibility_posts_and_returns_report(self, app_client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.governance.refresh_eligibility",
            lambda tid: _fake_report(False),
        )
        response = app_client.post(
            "/api/v1/governance/eligibility/refresh", headers=_auth_headers()
        )
        assert response.status_code == 200
        payload = response.get_json()["data"]
        assert payload["is_eligible"] is False


# ---------------------------------------------------------------------
# Tenant context
# ---------------------------------------------------------------------

class TestDossierEndpoint:
    def _fake_data(self) -> dict[str, Any]:
        return {
            "template_version": "v1",
            "generated_at": "2026-04-20T00:00:00+00:00",
            "eligibility": {"is_eligible": True},
            "fail_count": 0,
            "warn_count": 1,
            "findings": [{"code": "legal_nature", "status": "pass", "message": "ok"}],
        }

    def test_dossier_json_default(self, app_client, monkeypatch):
        data = self._fake_data()
        monkeypatch.setattr(
            "src.web.routes.governance.build_dossier_data", lambda tid: data
        )
        monkeypatch.setattr(
            "src.web.routes.governance.render_dossier_markdown",
            lambda tid, data=None: "# Dossie\n\nconteudo renderizado",
        )
        response = app_client.get("/api/v1/governance/eligibility/dossier")
        assert response.status_code == 200
        payload = response.get_json()["data"]
        assert payload["tenant_id"] == TENANT_ID
        assert payload["is_eligible"] is True
        assert payload["markdown"].startswith("# Dossie")
        assert payload["template_version"] == "v1"

    def test_dossier_format_md(self, app_client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.governance.build_dossier_data", lambda tid: self._fake_data()
        )
        monkeypatch.setattr(
            "src.web.routes.governance.render_dossier_markdown",
            lambda tid, data=None: "# MD puro",
        )
        response = app_client.get("/api/v1/governance/eligibility/dossier?format=md")
        assert response.status_code == 200
        assert "text/markdown" in response.headers["Content-Type"]
        assert response.get_data(as_text=True) == "# MD puro"

    def test_dossier_invalid_format_returns_422(self, app_client):
        response = app_client.get("/api/v1/governance/eligibility/dossier?format=pdf")
        assert response.status_code == 422
        assert response.get_json()["error"]["code"] == "validation_error"

    def test_dossier_missing_tenant_returns_404(self, app_client, monkeypatch):
        def raise_missing(_tid):
            raise ValueError("Tenant 42 nao encontrado.")

        monkeypatch.setattr(
            "src.web.routes.governance.build_dossier_data", raise_missing
        )
        response = app_client.get("/api/v1/governance/eligibility/dossier")
        assert response.status_code == 404
        assert response.get_json()["error"]["code"] == "not_found"


class TestAdminEndpoints:
    def test_admin_list_associations_returns_summary(self, app_client, monkeypatch):
        stub = [
            {"tenant_id": 1, "legal_name": "A1", "rt_count": 2,
             "has_capacity": True, "has_statute": False},
            {"tenant_id": 2, "legal_name": "A2", "rt_count": 0,
             "has_capacity": False, "has_statute": True},
        ]
        monkeypatch.setattr(
            "src.web.routes.governance.list_all_associations_summary",
            lambda: stub,
        )
        response = app_client.get("/api/v1/governance/admin/associations")
        assert response.status_code == 200
        payload = response.get_json()["data"]
        assert payload["count"] == 2
        assert payload["associations"][0]["legal_name"] == "A1"

    def test_admin_endpoint_does_not_need_tenant_context(
        self, no_tenant_client, monkeypatch
    ):
        """Endpoint multi-tenant nao depende de g.tenant_id."""
        monkeypatch.setattr(
            "src.web.routes.governance.list_all_associations_summary",
            lambda: [],
        )
        response = no_tenant_client.get("/api/v1/governance/admin/associations")
        assert response.status_code == 200
        assert response.get_json()["data"]["count"] == 0


class TestTenantContext:
    def test_missing_tenant_returns_400(self, no_tenant_client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.governance.repo.get_association", lambda _tid: None
        )
        response = no_tenant_client.get("/api/v1/governance/association")
        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "tenant_context_missing"
