"""Tests do blueprint regulatory_reporting (F3.7 do SCC).

Sem DB. Repositorio mockado via monkeypatch — foco e a camada HTTP:
parsing de query params, validacao de whitelists, codigos de erro,
serializacao e a logica de overview.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from flask import Flask, g
from flask_login import LoginManager

from src.web.auth_identity import AppUser
from src.web.routes.regulatory_reporting import (
    compute_indicators_score,
    compute_overview,
    regulatory_reporting_bp,
)


TENANT_ID = 42
ADMIN_ID = 99


@pytest.fixture
def client():
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

    app.register_blueprint(regulatory_reporting_bp)

    with app.test_client() as c:
        with c.session_transaction() as session:
            session["_user_id"] = str(ADMIN_ID)
        yield c


@pytest.fixture
def no_tenant_client():
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == str(ADMIN_ID):
            return AppUser(user_id=ADMIN_ID, username="admin", role="Admin")
        return None

    app.register_blueprint(regulatory_reporting_bp)

    with app.test_client() as c:
        with c.session_transaction() as session:
            session["_user_id"] = str(ADMIN_ID)
        yield c


def _project_row(**overrides: Any) -> dict[str, Any]:
    base = dict(
        id=1, tenant_id=TENANT_ID,
        project_code="PROJ-001", title="Projeto Teste",
        status="active",
        submitted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        approved_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
        started_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        concluded_at=None,
        anvisa_reference="ANVISA-XYZ",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return base


def _indicator_row(**overrides: Any) -> dict[str, Any]:
    base = dict(
        indicator_id=10, project_id=1, tenant_id=TENANT_ID,
        indicator_code="IND-A", indicator_name="Indicador A",
        unit="pct", target_value=80.0,
        reporting_frequency="monthly", is_mandatory=True,
        latest_value=82.0,
        latest_period_start=datetime(2026, 4, 1, tzinfo=timezone.utc),
        latest_period_end=datetime(2026, 4, 30, tzinfo=timezone.utc),
        latest_calculated_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        n_periods=3, on_target=True,
    )
    base.update(overrides)
    return base


def _submission_row(**overrides: Any) -> dict[str, Any]:
    base = dict(
        id=1, tenant_id=TENANT_ID, project_id=1,
        submission_type="monthly_report",
        submitted_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        submitted_by=ADMIN_ID,
        payload_uri="/storage/sub.json",
        payload_hash="a" * 64,
        anvisa_response_uri=None,
        anvisa_response_at=None,
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return base


def _report_row(**overrides: Any) -> dict[str, Any]:
    base = dict(
        id=1, tenant_id=TENANT_ID, project_id=1,
        report_type="monitoring_plan", version="v1.0",
        content_uri="/storage/rep.md",
        content_hash="b" * 64,
        generated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        approved_by=ADMIN_ID,
        approved_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return base


# =====================================================================
# Aggregations puras
# =====================================================================


class TestAggregations:
    def test_compute_indicators_score_zero_when_no_mandatory(self):
        assert compute_indicators_score({}) == 0
        assert compute_indicators_score({"mandatory_total": 0}) == 0

    def test_compute_indicators_score_percentage(self):
        score = compute_indicators_score({
            "mandatory_total": 4,
            "mandatory_on_target": 3,
        })
        assert score == 75

    def test_compute_overview_aggregates_active_or_pending(self):
        out = compute_overview(
            tenant_id=TENANT_ID,
            projects_by_status={"draft": 1, "active": 2, "concluded": 3},
            indicator_counts={"mandatory_total": 2, "mandatory_on_target": 1},
            submissions_pending=4,
            reports_by_type={"monitoring_plan": 1, "work_plan": 2},
        )
        assert out["projects"]["total"] == 6
        # active + submitted + under_review + approved
        assert out["projects"]["active_or_pending"] == 2
        assert out["indicators"]["score"] == 50
        assert out["submissions"]["awaiting_anvisa_response"] == 4
        assert out["reports"]["total"] == 3
        assert out["tenant_id"] == TENANT_ID


# =====================================================================
# /projects
# =====================================================================


class TestListProjects:
    def test_returns_serialized_list(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.list_projects",
            lambda tid, **kw: [_project_row(id=1), _project_row(id=2)],
        )
        resp = client.get("/api/v1/regulatory-reporting/projects")
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]["projects"]) == 2
        assert body["meta"]["count"] == 2
        # Datetime serializado para ISO
        assert body["data"]["projects"][0]["submitted_at"].startswith("2026-")

    def test_passes_filters(self, client, monkeypatch):
        captured: dict[str, Any] = {}

        def fake(tid, **kw):
            captured.update(kw, tid=tid)
            return []

        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.list_projects", fake
        )
        client.get("/api/v1/regulatory-reporting/projects?status=active&limit=50")
        assert captured["status"] == "active"
        assert captured["limit"] == 50

    def test_rejects_invalid_status(self, client):
        resp = client.get(
            "/api/v1/regulatory-reporting/projects?status=fake"
        )
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "validation_error"

    def test_no_tenant_returns_400(self, no_tenant_client):
        resp = no_tenant_client.get("/api/v1/regulatory-reporting/projects")
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "tenant_context_missing"


# =====================================================================
# /projects/<id>
# =====================================================================


class TestGetProject:
    def test_returns_project_with_protocol(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.get_project",
            lambda pid, *, tenant_id: _project_row(id=pid),
        )
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.get_active_protocol",
            lambda pid, *, tenant_id: {
                "id": 5, "project_id": pid, "protocol_version": "v1.0",
                "scope": {}, "applicable_norms": {}, "modulated_norms": {},
                "monitoring_parameters": {}, "discontinuity_plan": {},
                "quality_requirements": {}, "data_sharing_obligations": {},
                "effective_from": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "effective_until": None,
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            },
        )
        resp = client.get("/api/v1/regulatory-reporting/projects/1")
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["project"]["id"] == 1
        assert body["active_protocol"]["protocol_version"] == "v1.0"
        assert body["active_protocol"]["is_active"] is True

    def test_returns_404_when_missing(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.get_project",
            lambda pid, *, tenant_id: None,
        )
        resp = client.get("/api/v1/regulatory-reporting/projects/999")
        assert resp.status_code == 404

    def test_returns_project_with_no_protocol(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.get_project",
            lambda pid, *, tenant_id: _project_row(id=pid),
        )
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.get_active_protocol",
            lambda pid, *, tenant_id: None,
        )
        resp = client.get("/api/v1/regulatory-reporting/projects/1")
        body = resp.get_json()["data"]
        assert body["active_protocol"] is None


# =====================================================================
# /indicators
# =====================================================================


class TestListIndicators:
    def test_returns_serialized_list(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.list_indicator_dashboard",
            lambda tid, **kw: [_indicator_row(indicator_id=10)],
        )
        resp = client.get("/api/v1/regulatory-reporting/indicators")
        body = resp.get_json()
        assert resp.status_code == 200
        assert body["data"]["indicators"][0]["latest_value"] == 82.0
        assert body["data"]["indicators"][0]["on_target"] is True

    def test_passes_filters(self, client, monkeypatch):
        captured: dict[str, Any] = {}
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.list_indicator_dashboard",
            lambda tid, **kw: captured.update(kw, tid=tid) or [],
        )
        client.get(
            "/api/v1/regulatory-reporting/indicators"
            "?project_id=7&only_mandatory=true&only_off_target=false"
        )
        assert captured["project_id"] == 7
        assert captured["only_mandatory"] is True
        assert captured["only_off_target"] is False

    def test_rejects_invalid_bool(self, client):
        resp = client.get(
            "/api/v1/regulatory-reporting/indicators?only_mandatory=maybe"
        )
        assert resp.status_code == 422


# =====================================================================
# /indicators/<id>
# =====================================================================


class TestGetIndicator:
    def test_returns_indicator_with_history(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.get_indicator_dashboard_row",
            lambda iid, *, tenant_id: _indicator_row(indicator_id=iid),
        )
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.list_indicator_history",
            lambda iid, **kw: [
                {
                    "id": 1, "indicator_id": iid,
                    "period_start": datetime(2026, 4, 1, tzinfo=timezone.utc),
                    "period_end": datetime(2026, 4, 30, tzinfo=timezone.utc),
                    "calculated_value": 82.0,
                    "calculation_details": {"foo": "bar"},
                    "calculated_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
                },
            ],
        )
        resp = client.get("/api/v1/regulatory-reporting/indicators/10")
        body = resp.get_json()["data"]
        assert body["indicator"]["indicator_id"] == 10
        assert len(body["history"]) == 1
        assert body["history"][0]["calculated_value"] == 82.0

    def test_returns_404_when_missing(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.get_indicator_dashboard_row",
            lambda iid, *, tenant_id: None,
        )
        resp = client.get("/api/v1/regulatory-reporting/indicators/999")
        assert resp.status_code == 404

    def test_rejects_invalid_since(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.get_indicator_dashboard_row",
            lambda iid, *, tenant_id: _indicator_row(indicator_id=iid),
        )
        resp = client.get(
            "/api/v1/regulatory-reporting/indicators/10?since=quando"
        )
        assert resp.status_code == 422


# =====================================================================
# /submissions
# =====================================================================


class TestListSubmissions:
    def test_returns_serialized_list(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.list_submissions",
            lambda tid, **kw: [
                _submission_row(id=1),
                _submission_row(
                    id=2,
                    anvisa_response_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
                    anvisa_response_uri="/storage/resp.json",
                ),
            ],
        )
        resp = client.get("/api/v1/regulatory-reporting/submissions")
        body = resp.get_json()["data"]
        assert len(body["submissions"]) == 2
        assert body["submissions"][0]["awaiting_response"] is True
        assert body["submissions"][1]["awaiting_response"] is False

    def test_passes_filters(self, client, monkeypatch):
        captured: dict[str, Any] = {}
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.list_submissions",
            lambda tid, **kw: captured.update(kw, tid=tid) or [],
        )
        client.get(
            "/api/v1/regulatory-reporting/submissions"
            "?project_id=7&submission_type=monthly_report"
            "&since=2026-01-01T00:00:00&awaiting_response=true&limit=50"
        )
        assert captured["project_id"] == 7
        assert captured["submission_type"] == "monthly_report"
        assert captured["awaiting_response"] is True
        assert captured["limit"] == 50


# =====================================================================
# /reports
# =====================================================================


class TestListReports:
    def test_returns_serialized_list(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.list_reports",
            lambda tid, **kw: [_report_row(id=1)],
        )
        resp = client.get("/api/v1/regulatory-reporting/reports")
        body = resp.get_json()["data"]
        assert body["reports"][0]["is_approved"] is True

    def test_rejects_invalid_report_type(self, client):
        resp = client.get(
            "/api/v1/regulatory-reporting/reports?report_type=hacker_plan"
        )
        assert resp.status_code == 422

    def test_passes_only_approved_filter(self, client, monkeypatch):
        captured: dict[str, Any] = {}
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.list_reports",
            lambda tid, **kw: captured.update(kw) or [],
        )
        client.get(
            "/api/v1/regulatory-reporting/reports?only_approved=false"
        )
        assert captured["only_approved"] is False


# =====================================================================
# /overview
# =====================================================================


class TestOverview:
    def test_overview_combines_all_aggregates(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.count_projects_by_status",
            lambda tid: {"draft": 1, "active": 2},
        )
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.count_indicators_status",
            lambda tid: {
                "mandatory_total": 4,
                "mandatory_with_value": 4,
                "mandatory_on_target": 3,
                "mandatory_off_target": 1,
            },
        )
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.count_submissions_pending",
            lambda tid: 5,
        )
        monkeypatch.setattr(
            "src.web.routes.regulatory_reporting.repo.count_reports_by_type",
            lambda tid: {"monitoring_plan": 2},
        )
        resp = client.get("/api/v1/regulatory-reporting/overview")
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["projects"]["total"] == 3
        assert body["projects"]["active_or_pending"] == 2
        assert body["indicators"]["score"] == 75
        assert body["submissions"]["awaiting_anvisa_response"] == 5
        assert body["reports"]["total"] == 2
        assert body["tenant_id"] == TENANT_ID

    def test_overview_no_tenant_returns_400(self, no_tenant_client):
        resp = no_tenant_client.get("/api/v1/regulatory-reporting/overview")
        assert resp.status_code == 400
