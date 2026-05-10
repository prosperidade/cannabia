"""Sprint 2 Track Audit — empty-data swallow -> 5xx explicito.

Cobre o pattern uniforme aplicado em 11 endpoints:
- OperationalError -> 503 com error.code "database_unavailable"
- Exception generico -> 500 com error.code "internal_error"
- clinical_intelligence.py:lab_analysis: 404 explicito quando patient_id
  passado mas paciente nao existe (separa "no rows" legitimo de erro tecnico).

Endpoints Tier-1 cobertos:
- GET /api/v1/admin/users (admin_users.list_users)
- GET /api/v1/org/dashboard (org_management.org_dashboard)
- GET /api/v1/org/patients (org_management.org_patients)
- GET /api/v1/clinical/intelligence (clinical_intelligence.intelligence_dashboard)
- GET /api/v1/clinical/lab (clinical_intelligence.lab_analysis) — inclui 404
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, g
from flask_login import LoginManager
from psycopg2 import OperationalError

from src.web.auth_identity import AppUser
from src.web.routes.admin_users import admin_users_bp
from src.web.routes.clinical_intelligence import clinical_intel_bp
from src.web.routes.org_management import org_management_bp


CLINIC_ID = 1
USER_ID = 7


def _build_app(*, role: str = "Admin") -> Flask:
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == str(USER_ID):
            return AppUser(user_id=USER_ID, username="dev_admin", role=role)
        return None

    @app.before_request
    def inject_clinic():
        g.clinic_id = CLINIC_ID

    app.register_blueprint(admin_users_bp)
    app.register_blueprint(clinical_intel_bp)
    app.register_blueprint(org_management_bp)
    return app


def _client(app: Flask, *, role: str = "Admin"):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["_user_id"] = str(USER_ID)
    return c


def _raises(exc):
    """Helper: retorna uma callable que sempre levanta `exc` quando chamada."""
    def _raise(*_a, **_kw):
        raise exc
    return _raise


# ---------------------------------------------------------------------------
# admin_users.list_users — GET /api/v1/admin/users
# ---------------------------------------------------------------------------


def test_admin_users_returns_503_on_operational_error():
    app = _build_app(role="Admin")
    with patch(
        "src.web.routes.admin_users.db_cursor",
        side_effect=_raises(OperationalError("DB down")),
    ):
        resp = _client(app).get("/api/v1/admin/users/")
    assert resp.status_code == 503
    assert resp.get_json()["error"]["code"] == "database_unavailable"


def test_admin_users_returns_500_on_generic_exception():
    app = _build_app(role="Admin")
    with patch(
        "src.web.routes.admin_users.db_cursor",
        side_effect=_raises(RuntimeError("boom")),
    ):
        resp = _client(app).get("/api/v1/admin/users/")
    assert resp.status_code == 500
    assert resp.get_json()["error"]["code"] == "internal_error"


# ---------------------------------------------------------------------------
# org_management.org_dashboard — GET /api/v1/org/dashboard
# ---------------------------------------------------------------------------


def test_org_dashboard_returns_503_on_operational_error():
    app = _build_app(role="Medico")
    with patch(
        "src.web.routes.org_management.db_cursor",
        side_effect=_raises(OperationalError("DB down")),
    ):
        resp = _client(app).get("/api/v1/org/dashboard")
    assert resp.status_code == 503
    assert resp.get_json()["error"]["code"] == "database_unavailable"


def test_org_dashboard_returns_500_on_generic_exception():
    app = _build_app(role="Medico")
    with patch(
        "src.web.routes.org_management.db_cursor",
        side_effect=_raises(RuntimeError("oops")),
    ):
        resp = _client(app).get("/api/v1/org/dashboard")
    assert resp.status_code == 500
    assert resp.get_json()["error"]["code"] == "internal_error"


# ---------------------------------------------------------------------------
# org_management.org_patients — GET /api/v1/org/patients
# ---------------------------------------------------------------------------


def test_org_patients_returns_503_on_operational_error():
    app = _build_app(role="Medico")
    with patch(
        "src.web.routes.org_management.db_cursor",
        side_effect=_raises(OperationalError("DB down")),
    ):
        resp = _client(app).get("/api/v1/org/patients")
    assert resp.status_code == 503
    assert resp.get_json()["error"]["code"] == "database_unavailable"


def test_org_patients_returns_500_on_generic_exception():
    app = _build_app(role="Medico")
    with patch(
        "src.web.routes.org_management.db_cursor",
        side_effect=_raises(RuntimeError("oops")),
    ):
        resp = _client(app).get("/api/v1/org/patients")
    assert resp.status_code == 500
    assert resp.get_json()["error"]["code"] == "internal_error"


# ---------------------------------------------------------------------------
# clinical_intelligence.intelligence_dashboard — GET /api/v1/clinical/intelligence
# ---------------------------------------------------------------------------


def test_clinical_intelligence_returns_503_on_operational_error():
    app = _build_app(role="Medico")
    with patch(
        "src.web.routes.clinical_intelligence.db_cursor",
        side_effect=_raises(OperationalError("DB down")),
    ):
        resp = _client(app).get("/api/v1/clinical/intelligence")
    assert resp.status_code == 503
    assert resp.get_json()["error"]["code"] == "database_unavailable"


def test_clinical_intelligence_returns_500_on_generic_exception():
    app = _build_app(role="Medico")
    with patch(
        "src.web.routes.clinical_intelligence.db_cursor",
        side_effect=_raises(RuntimeError("oops")),
    ):
        resp = _client(app).get("/api/v1/clinical/intelligence")
    assert resp.status_code == 500
    assert resp.get_json()["error"]["code"] == "internal_error"


# ---------------------------------------------------------------------------
# clinical_intelligence.lab_analysis — GET /api/v1/clinical/lab
# Cobre 503, 500 e 404 (patient_id passado mas paciente nao existe).
# ---------------------------------------------------------------------------


def test_clinical_lab_returns_503_on_operational_error():
    app = _build_app(role="Medico")
    with patch(
        "src.web.routes.clinical_intelligence.db_cursor",
        side_effect=_raises(OperationalError("DB down")),
    ):
        resp = _client(app).get("/api/v1/clinical/lab")
    assert resp.status_code == 503
    assert resp.get_json()["error"]["code"] == "database_unavailable"


def test_clinical_lab_returns_500_on_generic_exception():
    app = _build_app(role="Medico")
    with patch(
        "src.web.routes.clinical_intelligence.db_cursor",
        side_effect=_raises(RuntimeError("oops")),
    ):
        resp = _client(app).get("/api/v1/clinical/lab")
    assert resp.status_code == 500
    assert resp.get_json()["error"]["code"] == "internal_error"


def test_clinical_lab_returns_404_when_patient_id_passed_but_not_found():
    """Sprint 2 Track Audit: lab_analysis separa 'no rows' legitimo
    (patient inexistente) de erro tecnico — devolve 404 explicito."""
    cursor = MagicMock()
    # Primeiro fetchone: SELECT da tabela patients -> None (nao encontrado)
    cursor.fetchone.return_value = None
    conn = MagicMock()

    @contextmanager
    def fake_db(dictionary=True):
        yield conn, cursor

    app = _build_app(role="Medico")
    with patch("src.web.routes.clinical_intelligence.db_cursor", fake_db):
        resp = _client(app).get("/api/v1/clinical/lab?patient_id=999")

    assert resp.status_code == 404
    assert resp.get_json()["error"]["code"] == "not_found"
