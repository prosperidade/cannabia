"""Tests do blueprint acompanhamento (P2 — KPIs reais em /org/acompanhamento).

Sem DB — service e mockado via monkeypatch. A camada HTTP (roles,
tenant context, contrato JSON) e o foco aqui.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from flask import Flask, g
from flask_login import LoginManager

from src.services.acompanhamento_service import (
    AcompanhamentoOverview,
    AgentActivity,
    KpiSnapshot,
)
from src.web.auth_identity import AppUser
from src.web.routes.acompanhamento import acompanhamento_bp


TENANT_ID = 42
USER_ID = 7


def _make_overview(**kpi_overrides: int) -> AcompanhamentoOverview:
    base_kpis: dict[str, int] = dict(
        patients_at_risk=2,
        followups_pending=5,
        triages_in_progress=1,
        adverse_events_open=3,
    )
    base_kpis.update(kpi_overrides)
    return AcompanhamentoOverview(
        tenant_id=TENANT_ID,
        generated_at=datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc),
        kpis=KpiSnapshot(**base_kpis),
        agents_activity_24h=(
            AgentActivity(agent="Triagem", actions=4, last_action_at="2026-04-27T11:30:00+00:00"),
            AgentActivity(agent="Anamnese", actions=2, last_action_at="2026-04-27T10:00:00+00:00"),
            AgentActivity(agent="FollowUp", actions=0, last_action_at=None),
            AgentActivity(agent="Regulatorio", actions=1, last_action_at="2026-04-27T09:30:00+00:00"),
        ),
    )


def _build_app(*, tenant_id: int | None = TENANT_ID, role: str = "Medico") -> Flask:
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == str(USER_ID):
            return AppUser(user_id=USER_ID, username="dev", role=role)
        return None

    if tenant_id is not None:
        @app.before_request
        def inject_tenant():
            g.tenant_id = tenant_id

    app.register_blueprint(acompanhamento_bp)
    return app


def _client(app: Flask):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["_user_id"] = str(USER_ID)
    return c


# ---------------------------------------------------------------------------
# GET /api/v1/org/acompanhamento/overview — happy path
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["Admin", "AdminClinica", "Medico", "Recepcao"])
def test_overview_allowed_roles(role: str, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_get_overview(tenant_id: int) -> AcompanhamentoOverview:
        captured["tenant_id"] = tenant_id
        return _make_overview()

    monkeypatch.setattr(
        "src.web.routes.acompanhamento.acompanhamento_service.get_overview",
        fake_get_overview,
    )

    app = _build_app(role=role)
    client = _client(app)

    resp = client.get("/api/v1/org/acompanhamento/overview")
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert "data" in body
    data = body["data"]

    assert captured["tenant_id"] == TENANT_ID
    assert data["tenant_id"] == TENANT_ID
    assert data["generated_at"] == "2026-04-27T12:00:00+00:00"
    assert data["kpis"] == {
        "patients_at_risk": 2,
        "followups_pending": 5,
        "triages_in_progress": 1,
        "adverse_events_open": 3,
    }
    agents = data["agents_activity_24h"]
    assert [a["agent"] for a in agents] == ["Triagem", "Anamnese", "FollowUp", "Regulatorio"]
    assert agents[0]["actions"] == 4
    assert agents[2]["last_action_at"] is None


def test_overview_rejects_financeiro(monkeypatch: pytest.MonkeyPatch) -> None:
    """Financeiro nao acessa /org/acompanhamento — usar /org/financeiro."""
    monkeypatch.setattr(
        "src.web.routes.acompanhamento.acompanhamento_service.get_overview",
        lambda tenant_id: _make_overview(),
    )
    app = _build_app(role="Financeiro")
    client = _client(app)

    resp = client.get("/api/v1/org/acompanhamento/overview")
    assert resp.status_code == 403


def test_overview_rejects_paciente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.web.routes.acompanhamento.acompanhamento_service.get_overview",
        lambda tenant_id: _make_overview(),
    )
    app = _build_app(role="Paciente")
    client = _client(app)

    resp = client.get("/api/v1/org/acompanhamento/overview")
    assert resp.status_code == 403


def test_overview_requires_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.web.routes.acompanhamento.acompanhamento_service.get_overview",
        lambda tenant_id: _make_overview(),
    )
    app = _build_app(role="Medico")
    client = app.test_client()  # sem login

    resp = client.get("/api/v1/org/acompanhamento/overview")
    assert resp.status_code == 401


def test_overview_missing_tenant_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.web.routes.acompanhamento.acompanhamento_service.get_overview",
        lambda tenant_id: _make_overview(),
    )
    app = _build_app(tenant_id=None, role="Medico")
    client = _client(app)

    resp = client.get("/api/v1/org/acompanhamento/overview")
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"]["code"] == "tenant_context_missing"


def test_overview_uses_clinic_id_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quando ``g.tenant_id`` ausente mas ``g.clinic_id`` existe, usa-o."""
    captured: dict[str, Any] = {}

    def fake_get_overview(tenant_id: int) -> AcompanhamentoOverview:
        captured["tenant_id"] = tenant_id
        return _make_overview()

    monkeypatch.setattr(
        "src.web.routes.acompanhamento.acompanhamento_service.get_overview",
        fake_get_overview,
    )

    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")
    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == str(USER_ID):
            return AppUser(user_id=USER_ID, username="dev", role="Medico")
        return None

    @app.before_request
    def inject_clinic():
        g.clinic_id = 99

    app.register_blueprint(acompanhamento_bp)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(USER_ID)

    resp = client.get("/api/v1/org/acompanhamento/overview")
    assert resp.status_code == 200, resp.get_json()
    assert captured["tenant_id"] == 99


# ---------------------------------------------------------------------------
# GET /api/v1/org/acompanhamento/active-patients
# ---------------------------------------------------------------------------

from src.services.acompanhamento_service import ActivePatientItem  # noqa: E402


def _make_active_patient(**overrides) -> ActivePatientItem:
    base: dict[str, Any] = dict(
        patient_id=1,
        patient_name="Maria",
        patient_phone="+5511999",
        plan_name="Plano CBD",
        dosage="5mg",
        frequency="2x/dia",
        plan_started_at="2026-04-01T00:00:00+00:00",
        days_in_treatment=28,
        next_return_date="2026-05-15T00:00:00+00:00",
        next_return_in_days=15,
        followup_status="sent",
        followup_type="d7",
        last_contact_at="2026-04-25T09:00:00+00:00",
    )
    base.update(overrides)
    return ActivePatientItem(**base)


@pytest.mark.parametrize("role", ["Admin", "AdminClinica", "Medico", "Recepcao"])
def test_active_patients_allowed_roles(role: str, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_active(tenant_id: int, limit: int = 20):
        captured["tenant_id"] = tenant_id
        captured["limit"] = limit
        return (
            _make_active_patient(patient_id=10, patient_name="Ana"),
            _make_active_patient(patient_id=11, patient_name="Joao", followup_status="responded"),
        )

    monkeypatch.setattr(
        "src.web.routes.acompanhamento.acompanhamento_service.get_active_patients",
        fake_active,
    )

    app = _build_app(role=role)
    resp = _client(app).get("/api/v1/org/acompanhamento/active-patients")
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()["data"]

    assert captured["tenant_id"] == TENANT_ID
    assert captured["limit"] == 20
    assert data["count"] == 2
    assert len(data["items"]) == 2
    item = data["items"][0]
    assert item["patient_id"] == 10
    assert item["patient_name"] == "Ana"
    assert item["plan_name"] == "Plano CBD"
    assert item["next_return_in_days"] == 15
    assert item["followup_status"] == "sent"


def test_active_patients_respects_limit_query(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_active(tenant_id: int, limit: int = 20):
        captured["limit"] = limit
        return ()

    monkeypatch.setattr(
        "src.web.routes.acompanhamento.acompanhamento_service.get_active_patients",
        fake_active,
    )

    app = _build_app()
    resp = _client(app).get("/api/v1/org/acompanhamento/active-patients?limit=50")
    assert resp.status_code == 200
    assert captured["limit"] == 50


def test_active_patients_clamps_limit_to_max(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_active(tenant_id: int, limit: int = 20):
        captured["limit"] = limit
        return ()

    monkeypatch.setattr(
        "src.web.routes.acompanhamento.acompanhamento_service.get_active_patients",
        fake_active,
    )

    app = _build_app()
    _client(app).get("/api/v1/org/acompanhamento/active-patients?limit=999")
    assert captured["limit"] == 100  # clamp em 100


def test_active_patients_falls_back_to_default_on_invalid_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_active(tenant_id: int, limit: int = 20):
        captured["limit"] = limit
        return ()

    monkeypatch.setattr(
        "src.web.routes.acompanhamento.acompanhamento_service.get_active_patients",
        fake_active,
    )

    app = _build_app()
    _client(app).get("/api/v1/org/acompanhamento/active-patients?limit=abc")
    assert captured["limit"] == 20


def test_active_patients_rejects_paciente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.web.routes.acompanhamento.acompanhamento_service.get_active_patients",
        lambda tenant_id, limit=20: (),
    )
    app = _build_app(role="Paciente")
    resp = _client(app).get("/api/v1/org/acompanhamento/active-patients")
    assert resp.status_code == 403


def test_active_patients_missing_tenant_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.web.routes.acompanhamento.acompanhamento_service.get_active_patients",
        lambda tenant_id, limit=20: (),
    )
    app = _build_app(tenant_id=None)
    resp = _client(app).get("/api/v1/org/acompanhamento/active-patients")
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"]["code"] == "tenant_context_missing"
