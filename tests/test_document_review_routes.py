"""Testes do blueprint document_reviews (F4.7 do SCC).

Usa Flask mini-app com o blueprint isolado + login manager simples,
mesmo padrao de test_governance_routes.py. Nao depende de DB real;
regras de negocio ja sao testadas em test_document_review_service.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from flask import Flask, g
from flask_login import LoginManager

from src.services.document_review_service import (
    InvalidTransitionError,
    ReportNotFoundError,
    ReviewStep,
)
from src.web.auth_identity import AppUser
from src.web.routes.document_reviews import document_reviews_bp


TENANT_ID = 42
OTHER_TENANT_ID = 99
ADMIN_ID = 10
MEDICO_ID = 11
PACIENTE_ID = 12
CSRF_TOKEN = "test-csrf-token"


def _build_app(role: str = "Admin", user_id: int = ADMIN_ID,
               username: str = "admin") -> Flask:
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(uid: str):
        if uid == str(user_id):
            return AppUser(user_id=user_id, username=username, role=role)
        return None

    @app.before_request
    def inject_tenant():
        g.tenant_id = TENANT_ID
        g.user_id = user_id

    app.register_blueprint(document_reviews_bp)
    return app


@pytest.fixture
def admin_client():
    app = _build_app(role="Admin", user_id=ADMIN_ID, username="admin")
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = str(ADMIN_ID)
            session["csrf_token"] = CSRF_TOKEN
        yield client


@pytest.fixture
def medico_client():
    app = _build_app(role="Medico", user_id=MEDICO_ID, username="medico")
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = str(MEDICO_ID)
            session["csrf_token"] = CSRF_TOKEN
        yield client


@pytest.fixture
def paciente_client():
    app = _build_app(role="Paciente", user_id=PACIENTE_ID, username="paciente")
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = str(PACIENTE_ID)
            session["csrf_token"] = CSRF_TOKEN
        yield client


@pytest.fixture
def csrf_headers():
    return {"Content-Type": "application/json", "X-CSRF-Token": CSRF_TOKEN}


def _make_step(**overrides) -> ReviewStep:
    defaults = dict(
        id=1, report_id=7,
        from_status="draft", to_status="rt_review",
        action="submit_to_rt", actor_user_id=ADMIN_ID,
        actor_role="admin", notes=None,
        content_hash_at_review="a" * 64,
        signature_hash="b" * 64,
        reviewed_at=datetime(2026, 4, 21, 12, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return ReviewStep(**defaults)


# =====================================================================
# POST /<id>/review
# =====================================================================

class TestPostReview:
    def test_happy_path_admin_submit_to_rt(self, admin_client, csrf_headers, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.document_reviews._load_report_tenant",
            lambda rid: TENANT_ID,
        )
        monkeypatch.setattr(
            "src.web.routes.document_reviews.transition",
            lambda *a, **kw: _make_step(),
        )
        resp = admin_client.post(
            "/api/v1/reports/7/review",
            json={"action": "submit_to_rt", "notes": "submetendo"},
            headers=csrf_headers,
        )
        assert resp.status_code == 201
        body = resp.get_json()["data"]
        assert body["new_status"] == "rt_review"
        assert body["step"]["action"] == "submit_to_rt"

    def test_medico_pode_acao_rt(self, medico_client, csrf_headers, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.document_reviews._load_report_tenant",
            lambda rid: TENANT_ID,
        )
        monkeypatch.setattr(
            "src.web.routes.document_reviews.transition",
            lambda *a, **kw: _make_step(
                from_status="rt_review", to_status="legal_review",
                action="rt_approve", actor_role="medico", actor_user_id=MEDICO_ID,
            ),
        )
        resp = medico_client.post(
            "/api/v1/reports/7/review",
            json={"action": "rt_approve"},
            headers=csrf_headers,
        )
        assert resp.status_code == 201

    def test_medico_nao_pode_legal_approve(self, medico_client, csrf_headers, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.document_reviews._load_report_tenant",
            lambda rid: TENANT_ID,
        )
        resp = medico_client.post(
            "/api/v1/reports/7/review",
            json={"action": "legal_approve"},
            headers=csrf_headers,
        )
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "forbidden"

    def test_paciente_nao_pode_nada(self, paciente_client, csrf_headers):
        resp = paciente_client.post(
            "/api/v1/reports/7/review",
            json={"action": "submit_to_rt"},
            headers=csrf_headers,
        )
        assert resp.status_code == 403

    def test_sem_action(self, admin_client, csrf_headers):
        resp = admin_client.post(
            "/api/v1/reports/7/review",
            json={"notes": "x"},
            headers=csrf_headers,
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "missing_action"

    def test_action_invalida(self, admin_client, csrf_headers):
        resp = admin_client.post(
            "/api/v1/reports/7/review",
            json={"action": "teleport"},
            headers=csrf_headers,
        )
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "invalid_action"

    def test_report_nao_encontrado(self, admin_client, csrf_headers, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.document_reviews._load_report_tenant",
            lambda rid: None,
        )
        resp = admin_client.post(
            "/api/v1/reports/999/review",
            json={"action": "submit_to_rt"},
            headers=csrf_headers,
        )
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "report_not_found"

    def test_report_de_outro_tenant(self, admin_client, csrf_headers, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.document_reviews._load_report_tenant",
            lambda rid: OTHER_TENANT_ID,
        )
        resp = admin_client.post(
            "/api/v1/reports/7/review",
            json={"action": "submit_to_rt"},
            headers=csrf_headers,
        )
        assert resp.status_code == 403

    def test_transicao_invalida_retorna_409(self, admin_client, csrf_headers, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.document_reviews._load_report_tenant",
            lambda rid: TENANT_ID,
        )
        def _raise(*a, **kw):
            raise InvalidTransitionError("nao pode")
        monkeypatch.setattr(
            "src.web.routes.document_reviews.transition", _raise
        )
        resp = admin_client.post(
            "/api/v1/reports/7/review",
            json={"action": "rt_approve"},
            headers=csrf_headers,
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "invalid_transition"

    def test_sem_csrf_bloqueia(self, admin_client):
        # Sem X-CSRF-Token o _require_json_csrf retorna csrf_invalid (400)
        resp = admin_client.post(
            "/api/v1/reports/7/review",
            json={"action": "submit_to_rt"},
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "csrf_invalid"


# =====================================================================
# GET /<id>/status
# =====================================================================

class TestGetStatus:
    def test_happy_path(self, admin_client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.document_reviews.get_report_status",
            lambda rid: {
                "report": {
                    "id": 7, "tenant_id": TENANT_ID, "status": "rt_review",
                    "content_hash": "a" * 64, "report_type": "work_plan",
                    "version": "v1", "current_stage_notes": None,
                    "approved_by": None, "approved_at": None,
                },
                "last_step": {"id": 1, "action": "submit_to_rt"},
            },
        )
        resp = admin_client.get("/api/v1/reports/7/status")
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["report"]["status"] == "rt_review"
        assert body["last_step"]["action"] == "submit_to_rt"

    def test_report_de_outro_tenant(self, admin_client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.document_reviews.get_report_status",
            lambda rid: {"report": {"id": 7, "tenant_id": OTHER_TENANT_ID,
                                    "status": "draft", "content_hash": "a"*64,
                                    "report_type": "x", "version": "v1",
                                    "current_stage_notes": None,
                                    "approved_by": None, "approved_at": None},
                        "last_step": None},
        )
        resp = admin_client.get("/api/v1/reports/7/status")
        assert resp.status_code == 403

    def test_report_nao_encontrado(self, admin_client, monkeypatch):
        def _raise(rid):
            raise ReportNotFoundError(f"Report {rid} nao encontrado.")
        monkeypatch.setattr(
            "src.web.routes.document_reviews.get_report_status", _raise
        )
        resp = admin_client.get("/api/v1/reports/999/status")
        assert resp.status_code == 404


# =====================================================================
# GET /<id>/history
# =====================================================================

class TestGetHistory:
    def test_retorna_lista_de_steps(self, admin_client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.document_reviews._load_report_tenant",
            lambda rid: TENANT_ID,
        )
        steps = [
            _make_step(id=1, from_status="draft", to_status="rt_review",
                       action="submit_to_rt"),
            _make_step(id=2, from_status="rt_review", to_status="legal_review",
                       action="rt_approve"),
        ]
        monkeypatch.setattr(
            "src.web.routes.document_reviews.list_workflow_steps",
            lambda rid: steps,
        )
        resp = admin_client.get("/api/v1/reports/7/history")
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert len(body) == 2
        assert body[0]["action"] == "submit_to_rt"
        assert body[1]["action"] == "rt_approve"

    def test_report_inexistente_retorna_404(self, admin_client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.document_reviews._load_report_tenant",
            lambda rid: None,
        )
        resp = admin_client.get("/api/v1/reports/999/history")
        assert resp.status_code == 404
