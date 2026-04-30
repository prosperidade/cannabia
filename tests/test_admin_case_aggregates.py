"""Tests do endpoint admin POST /api/v1/admin/case-aggregates/run (C7)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from flask import Flask
from flask_login import LoginManager

from src.knowledge.case_aggregator import CaseAggregate, CaseGroupKey
from src.web.auth_identity import AppUser
from src.web.routes.admin_case_aggregates import admin_case_aggregates_bp


USER_ID = 1
CSRF_TOKEN = "test-csrf-token"


def _build_app(*, role: str = "Admin") -> Flask:
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret", WTF_CSRF_ENABLED=False)

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == str(USER_ID):
            return AppUser(user_id=USER_ID, username="admin", role=role)
        return None

    app.register_blueprint(admin_case_aggregates_bp)
    return app


def _client(app: Flask):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["_user_id"] = str(USER_ID)
        sess["csrf_token"] = CSRF_TOKEN
    return c


def _csrf_headers():
    return {"X-CSRF-Token": CSRF_TOKEN, "Content-Type": "application/json"}


def _make_agg(n_patients: int = 8) -> CaseAggregate:
    return CaseAggregate(
        key=CaseGroupKey(
            condition="epilepsia",
            age_range="30-49",
            dose_range="5-10mg",
            ratio_class="cbd_dominante",
        ),
        n_patients=n_patients,
        period_start="2026-01-01",
        period_end="2026-04-29",
        tenants_contributing=2,
        median_dose_mg=7.0,
        title="Epilepsia | 30-49 anos | 5-10mg | CBD dominante (n=8)",
        abstract="Coorte clinica anonimizada de 8 pacientes...",
        tags=["case_aggregate", "condition:epilepsia"],
    )


# ─────────────────────────────────────────────────────────────────
# Roles
# ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("role", ["AdminClinica", "Medico", "Recepcao", "Financeiro", "Paciente"])
def test_run_rejects_non_admin_roles(role):
    app = _build_app(role=role)
    resp = _client(app).post("/api/v1/admin/case-aggregates/run")
    assert resp.status_code == 403


def test_run_requires_authentication():
    app = _build_app()
    resp = app.test_client().post("/api/v1/admin/case-aggregates/run")
    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────
# Pipeline + persist
# ─────────────────────────────────────────────────────────────────


def test_run_persists_aggregates_by_default():
    captured: dict[str, Any] = {}

    def fake_aggregate(*, min_group_size, lookback_days, now=None):
        captured["min_group_size"] = min_group_size
        captured["lookback_days"] = lookback_days
        return [_make_agg()]

    def fake_persist(aggregates, *, user_id=None):
        captured["persisted"] = list(aggregates)
        captured["user_id"] = user_id
        return {"inserted": 1, "refreshed_stale": 0}

    app = _build_app()
    with patch("src.web.routes.admin_case_aggregates.aggregate_clinical_cases", side_effect=fake_aggregate), \
         patch("src.web.routes.admin_case_aggregates.persist_aggregates_to_catalog", side_effect=fake_persist):
        resp = _client(app).post("/api/v1/admin/case-aggregates/run", json={}, headers=_csrf_headers())

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["groups_total"] == 1
    assert data["patients_covered"] == 8
    assert data["dry_run"] is False
    assert data["persisted"] == {"inserted": 1, "refreshed_stale": 0}
    assert captured["user_id"] == USER_ID


def test_run_dry_run_skips_persistence():
    captured: dict[str, Any] = {"persisted_called": False}

    def fake_aggregate(*, min_group_size, lookback_days, now=None):
        return [_make_agg(), _make_agg(n_patients=12)]

    def fake_persist(aggregates, *, user_id=None):
        captured["persisted_called"] = True
        return {"inserted": 99, "refreshed_stale": 0}

    app = _build_app()
    with patch("src.web.routes.admin_case_aggregates.aggregate_clinical_cases", side_effect=fake_aggregate), \
         patch("src.web.routes.admin_case_aggregates.persist_aggregates_to_catalog", side_effect=fake_persist):
        resp = _client(app).post("/api/v1/admin/case-aggregates/run", json={"dry_run": True}, headers=_csrf_headers())

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["dry_run"] is True
    assert data["persisted"] == {"inserted": 0, "refreshed_stale": 0}
    assert captured["persisted_called"] is False


def test_run_clamps_lookback_and_k():
    captured: dict[str, Any] = {}

    def fake_aggregate(*, min_group_size, lookback_days, now=None):
        captured["min_group_size"] = min_group_size
        captured["lookback_days"] = lookback_days
        return []

    app = _build_app()
    with patch("src.web.routes.admin_case_aggregates.aggregate_clinical_cases", side_effect=fake_aggregate):
        # lookback acima do max => clamp em 730
        # min_group_size acima do max => clamp em 50
        resp = _client(app).post(
            "/api/v1/admin/case-aggregates/run",
            json={"lookback_days": 9999, "min_group_size": 999},
            headers=_csrf_headers(),
        )

    assert resp.status_code == 200
    assert captured["lookback_days"] == 730
    assert captured["min_group_size"] == 50


def test_run_falls_back_to_defaults_on_invalid_payload():
    captured: dict[str, Any] = {}

    def fake_aggregate(*, min_group_size, lookback_days, now=None):
        captured["min_group_size"] = min_group_size
        captured["lookback_days"] = lookback_days
        return []

    app = _build_app()
    with patch("src.web.routes.admin_case_aggregates.aggregate_clinical_cases", side_effect=fake_aggregate):
        resp = _client(app).post(
            "/api/v1/admin/case-aggregates/run",
            json={"lookback_days": "abc", "min_group_size": "bad"},
            headers=_csrf_headers(),
        )

    from src.knowledge.case_aggregator import DEFAULT_LOOKBACK_DAYS, MIN_K
    assert resp.status_code == 200
    assert captured["lookback_days"] == DEFAULT_LOOKBACK_DAYS
    assert captured["min_group_size"] == MIN_K


def test_run_returns_zeros_when_no_groups():
    def fake_aggregate(*, min_group_size, lookback_days, now=None):
        return []

    app = _build_app()
    with patch("src.web.routes.admin_case_aggregates.aggregate_clinical_cases", side_effect=fake_aggregate), \
         patch("src.web.routes.admin_case_aggregates.persist_aggregates_to_catalog") as persist:
        resp = _client(app).post("/api/v1/admin/case-aggregates/run", json={}, headers=_csrf_headers())

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["groups_total"] == 0
    assert data["patients_covered"] == 0
    assert data["persisted"] == {"inserted": 0, "refreshed_stale": 0}
    persist.assert_not_called()


# ─────────────────────────────────────────────────────────────────
# GET /last
# ─────────────────────────────────────────────────────────────────


def test_last_returns_recent_aggregates():
    from contextlib import contextmanager
    from datetime import datetime
    from unittest.mock import MagicMock

    rows = [
        {
            "id": 11,
            "title": "Epilepsia | 30-49 anos | 5-10mg | CBD dominante (n=8)",
            "abstract": "Coorte de 8 pacientes...",
            "ingested_at": datetime(2026, 4, 29, 10, 0),
            "case_aggregate_metadata": {"k_anonymity_n": 8},
        },
        {
            "id": 12,
            "title": "Dor cronica | 50-69 anos | 10-20mg | balanceado (n=15)",
            "abstract": "Coorte de 15 pacientes...",
            "ingested_at": datetime(2026, 4, 28, 9, 0),
            "case_aggregate_metadata": {"k_anonymity_n": 15},
        },
    ]
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    conn = MagicMock()

    @contextmanager
    def fake_db_cursor(dictionary=True):
        yield conn, cursor

    app = _build_app()
    with patch("src.web.routes.admin_case_aggregates.db_cursor", fake_db_cursor):
        resp = _client(app).get("/api/v1/admin/case-aggregates/last?limit=2")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["count"] == 2
    assert data["items"][0]["id"] == 11
    assert data["items"][0]["metadata"]["k_anonymity_n"] == 8
