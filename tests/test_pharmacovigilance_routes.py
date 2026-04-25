"""Tests do blueprint pharmacovigilance (F3.6 do SCC).

Sem DB — service e adverse_event_service sao mockados via monkeypatch.
A camada HTTP (parsing de payload, codigos de erro, contrato JSON) e
o foco aqui. Cobertura de orquestracao real fica em
test_pharmacovigilance_service.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from flask import Flask, g
from flask_login import LoginManager

from src.services.adverse_event_service import (
    AdverseEvent,
    AdverseEventValidationError,
)
from src.services.pharmacovigilance_service import (
    AdverseEventNotFoundError,
    DashboardSummary,
    NotificationRecord,
)
from src.web.auth_identity import AppUser
from src.web.routes.pharmacovigilance import pharmacovigilance_bp


TENANT_ID = 42
ADMIN_ID = 99
CSRF_TOKEN = "test-csrf-token"


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

    app.register_blueprint(pharmacovigilance_bp)

    with app.test_client() as c:
        with c.session_transaction() as session:
            session["_user_id"] = str(ADMIN_ID)
            session["csrf_token"] = CSRF_TOKEN
        yield c


@pytest.fixture
def no_tenant_client():
    """Variante sem ``g.tenant_id`` para testar erro de contexto."""
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == str(ADMIN_ID):
            return AppUser(user_id=ADMIN_ID, username="admin", role="Admin")
        return None

    app.register_blueprint(pharmacovigilance_bp)

    with app.test_client() as c:
        with c.session_transaction() as session:
            session["_user_id"] = str(ADMIN_ID)
            session["csrf_token"] = CSRF_TOKEN
        yield c


def _auth_headers() -> dict[str, str]:
    return {"Content-Type": "application/json", "X-CSRF-Token": CSRF_TOKEN}


def _make_event(**overrides: Any) -> AdverseEvent:
    base: dict[str, Any] = dict(
        id=1,
        tenant_id=TENANT_ID,
        member_id=None,
        preparation_id=None,
        reported_at=datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc),
        event_onset_at=None,
        severity="mild",
        description="evento teste",
        reported_via="web",
        ai_triage_result=None,
        triaged_by=None,
        clinical_assessment=None,
        outcome=None,
        created_at=datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return AdverseEvent(**base)


def _make_notification(**overrides: Any) -> NotificationRecord:
    base: dict[str, Any] = dict(
        id=10,
        adverse_event_id=1,
        notification_target="internal_only",
        notified_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
        notification_reference="MOCK-XYZ",
        response_received_at=None,
        response_payload={"accepted": True},
        created_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return NotificationRecord(**base)


# =====================================================================
# POST /adverse-events — captura
# =====================================================================


class TestCaptureEndpoint:
    def test_captures_minimal_payload(self, client, monkeypatch):
        captured: dict[str, Any] = {}

        def fake_capture(**kwargs):
            captured.update(kwargs)
            return _make_event(
                id=7,
                description=kwargs["description"],
                severity=kwargs["severity"],
                reported_via=kwargs["reported_via"],
            )

        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.adverse_event_service.capture_adverse_event",
            fake_capture,
        )

        resp = client.post(
            "/api/v1/pharmacovigilance/adverse-events",
            headers=_auth_headers(),
            json={
                "description": "Paciente com tontura.",
                "severity": "mild",
                "reported_via": "web",
            },
        )
        assert resp.status_code == 201
        body = resp.get_json()["data"]
        assert body["adverse_event"]["id"] == 7
        assert captured["tenant_id"] == TENANT_ID
        assert captured["description"] == "Paciente com tontura."

    def test_rejects_missing_description(self, client):
        resp = client.post(
            "/api/v1/pharmacovigilance/adverse-events",
            headers=_auth_headers(),
            json={"severity": "mild", "reported_via": "web"},
        )
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "validation_error"

    def test_rejects_missing_severity(self, client):
        resp = client.post(
            "/api/v1/pharmacovigilance/adverse-events",
            headers=_auth_headers(),
            json={"description": "x", "reported_via": "web"},
        )
        assert resp.status_code == 422

    def test_rejects_missing_reported_via(self, client):
        resp = client.post(
            "/api/v1/pharmacovigilance/adverse-events",
            headers=_auth_headers(),
            json={"description": "x", "severity": "mild"},
        )
        assert resp.status_code == 422

    def test_rejects_invalid_iso_dates(self, client):
        resp = client.post(
            "/api/v1/pharmacovigilance/adverse-events",
            headers=_auth_headers(),
            json={
                "description": "x",
                "severity": "mild",
                "reported_via": "web",
                "reported_at": "not-a-date",
            },
        )
        assert resp.status_code == 422

    def test_propagates_service_validation_error(self, client, monkeypatch):
        def boom(**kwargs):
            raise AdverseEventValidationError("severity invalida")

        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.adverse_event_service.capture_adverse_event",
            boom,
        )
        resp = client.post(
            "/api/v1/pharmacovigilance/adverse-events",
            headers=_auth_headers(),
            json={
                "description": "x",
                "severity": "catastrophic",
                "reported_via": "web",
            },
        )
        assert resp.status_code == 422
        assert "severity" in resp.get_json()["error"]["message"]

    def test_no_tenant_context_returns_400(self, no_tenant_client):
        resp = no_tenant_client.post(
            "/api/v1/pharmacovigilance/adverse-events",
            headers=_auth_headers(),
            json={
                "description": "x", "severity": "mild", "reported_via": "web"
            },
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "tenant_context_missing"


# =====================================================================
# GET /adverse-events — list
# =====================================================================


class TestListEndpoint:
    def test_list_returns_serialized_events(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.adverse_event_service.list_events",
            lambda *a, **kw: [_make_event(id=1), _make_event(id=2, severity="severe")],
        )
        resp = client.get("/api/v1/pharmacovigilance/adverse-events")
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]["adverse_events"]) == 2
        assert body["meta"]["count"] == 2
        # severe events expoem requires_regulatory_notification=True
        ev2 = body["data"]["adverse_events"][1]
        assert ev2["severity"] == "severe"
        assert ev2["requires_regulatory_notification"] is True

    def test_list_passes_filters(self, client, monkeypatch):
        captured: dict[str, Any] = {}

        def fake_list(tid, **kwargs):
            captured["tid"] = tid
            captured.update(kwargs)
            return []

        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.adverse_event_service.list_events",
            fake_list,
        )
        resp = client.get(
            "/api/v1/pharmacovigilance/adverse-events"
            "?severity=severe&reported_via=consultation"
            "&since=2026-01-01T00:00:00&has_triage=true&limit=50"
        )
        assert resp.status_code == 200
        assert captured["tid"] == TENANT_ID
        assert captured["severity"] == "severe"
        assert captured["reported_via"] == "consultation"
        assert captured["has_triage"] is True
        assert captured["limit"] == 50

    def test_list_rejects_invalid_has_triage(self, client):
        resp = client.get(
            "/api/v1/pharmacovigilance/adverse-events?has_triage=maybe"
        )
        assert resp.status_code == 422

    def test_list_rejects_invalid_since(self, client):
        resp = client.get(
            "/api/v1/pharmacovigilance/adverse-events?since=quando"
        )
        assert resp.status_code == 422

    def test_list_clamps_limit(self, client, monkeypatch):
        captured: dict[str, Any] = {}
        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.adverse_event_service.list_events",
            lambda tid, **kw: captured.update(kw) or [],
        )
        client.get("/api/v1/pharmacovigilance/adverse-events?limit=999999")
        assert captured["limit"] == 500

    def test_list_propagates_service_validation_error(self, client, monkeypatch):
        def boom(tid, **kw):
            raise AdverseEventValidationError("severity invalida")

        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.adverse_event_service.list_events",
            boom,
        )
        resp = client.get(
            "/api/v1/pharmacovigilance/adverse-events?severity=fake"
        )
        assert resp.status_code == 422


# =====================================================================
# GET /adverse-events/<id> — detail
# =====================================================================


class TestDetailEndpoint:
    def test_returns_event(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.adverse_event_service.get_event",
            lambda eid, *, tenant_id: _make_event(id=eid),
        )
        resp = client.get("/api/v1/pharmacovigilance/adverse-events/123")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["adverse_event"]["id"] == 123

    def test_returns_404_when_missing(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.adverse_event_service.get_event",
            lambda eid, *, tenant_id: None,
        )
        resp = client.get("/api/v1/pharmacovigilance/adverse-events/999")
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "not_found"


# =====================================================================
# PUT clinical-assessment / outcome
# =====================================================================


class TestUpdateEndpoints:
    def test_set_clinical_assessment(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.adverse_event_service.set_clinical_assessment",
            lambda eid, *, tenant_id, assessment: _make_event(
                id=eid, clinical_assessment=assessment
            ),
        )
        resp = client.put(
            "/api/v1/pharmacovigilance/adverse-events/5/clinical-assessment",
            headers=_auth_headers(),
            json={"assessment": "Reacao auto-limitada."},
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["adverse_event"][
            "clinical_assessment"
        ] == "Reacao auto-limitada."

    def test_set_clinical_assessment_validates_empty(self, client, monkeypatch):
        def boom(*a, **kw):
            raise AdverseEventValidationError("assessment vazio")

        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.adverse_event_service.set_clinical_assessment",
            boom,
        )
        resp = client.put(
            "/api/v1/pharmacovigilance/adverse-events/5/clinical-assessment",
            headers=_auth_headers(),
            json={"assessment": ""},
        )
        assert resp.status_code == 422

    def test_set_clinical_assessment_returns_404(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.adverse_event_service.set_clinical_assessment",
            lambda *a, **kw: None,
        )
        resp = client.put(
            "/api/v1/pharmacovigilance/adverse-events/9/clinical-assessment",
            headers=_auth_headers(),
            json={"assessment": "x"},
        )
        assert resp.status_code == 404

    def test_set_outcome(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.adverse_event_service.set_outcome",
            lambda eid, *, tenant_id, outcome: _make_event(
                id=eid, outcome=outcome
            ),
        )
        resp = client.put(
            "/api/v1/pharmacovigilance/adverse-events/5/outcome",
            headers=_auth_headers(),
            json={"outcome": "resolved"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["adverse_event"]["outcome"] == "resolved"


# =====================================================================
# POST /<id>/triage — F3.4
# =====================================================================


class TestTriageEndpoint:
    def test_triage_returns_skill_payload(self, client, monkeypatch):
        triage_result = {
            "ok": True,
            "severity_reported": "moderate",
            "severity_suggested": "severe",
            "escalated": True,
            "notify_required": True,
            "red_flags": ["internado"],
            "matched_by_level": {"severe": ["internado"]},
            "reasoning": "...",
            "model_version": "regulatorio-triage-v1-heuristic",
            "event": _make_event(id=5, severity="moderate"),
        }
        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.pharmacovigilance_service.triage_event",
            lambda eid, *, tenant_id, triaged_by=None: triage_result,
        )
        resp = client.post(
            "/api/v1/pharmacovigilance/adverse-events/5/triage",
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["severity_suggested"] == "severe"
        assert body["notify_required"] is True
        assert body["model_version"].startswith("regulatorio-triage-")
        assert "adverse_event" in body  # estado pos-update veio anexo

    def test_triage_returns_404(self, client, monkeypatch):
        def boom(*a, **kw):
            raise AdverseEventNotFoundError("evento 999 nao encontrado")

        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.pharmacovigilance_service.triage_event",
            boom,
        )
        resp = client.post(
            "/api/v1/pharmacovigilance/adverse-events/999/triage",
            headers=_auth_headers(),
        )
        assert resp.status_code == 404


# =====================================================================
# POST /<id>/notify — F3.5
# =====================================================================


class TestNotifyEndpoint:
    def test_notify_returns_201_with_record(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.pharmacovigilance_service.notify_event",
            lambda eid, *, tenant_id, provider=None: _make_notification(
                adverse_event_id=eid
            ),
        )
        resp = client.post(
            "/api/v1/pharmacovigilance/adverse-events/5/notify",
            headers=_auth_headers(),
            json={},
        )
        assert resp.status_code == 201
        body = resp.get_json()["data"]
        assert body["notification"]["notification_target"] == "internal_only"
        assert body["notification"]["notification_reference"] == "MOCK-XYZ"

    def test_notify_passes_provider(self, client, monkeypatch):
        captured: dict[str, Any] = {}

        def fake(eid, *, tenant_id, provider=None):
            captured["eid"] = eid
            captured["provider"] = provider
            return _make_notification(adverse_event_id=eid)

        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.pharmacovigilance_service.notify_event",
            fake,
        )
        client.post(
            "/api/v1/pharmacovigilance/adverse-events/5/notify",
            headers=_auth_headers(),
            json={"provider": "vigimed"},
        )
        assert captured["provider"] == "vigimed"

    def test_notify_returns_404_for_missing_event(self, client, monkeypatch):
        def boom(*a, **kw):
            raise AdverseEventNotFoundError("evento nao encontrado")

        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.pharmacovigilance_service.notify_event",
            boom,
        )
        resp = client.post(
            "/api/v1/pharmacovigilance/adverse-events/999/notify",
            headers=_auth_headers(),
            json={},
        )
        assert resp.status_code == 404

    def test_notify_returns_422_for_unknown_provider(self, client, monkeypatch):
        from src.integrations.vigimed import UnknownProviderError

        def boom(*a, **kw):
            raise UnknownProviderError("provider 'fake' invalido")

        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.pharmacovigilance_service.notify_event",
            boom,
        )
        resp = client.post(
            "/api/v1/pharmacovigilance/adverse-events/5/notify",
            headers=_auth_headers(),
            json={"provider": "fake"},
        )
        assert resp.status_code == 422

    def test_notify_returns_502_for_submission_failure(
        self, client, monkeypatch
    ):
        from src.integrations.vigimed import VigiMedSubmissionError

        def boom(*a, **kw):
            raise VigiMedSubmissionError("Vigimed real nao plugado")

        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.pharmacovigilance_service.notify_event",
            boom,
        )
        resp = client.post(
            "/api/v1/pharmacovigilance/adverse-events/5/notify",
            headers=_auth_headers(),
            json={"provider": "vigimed"},
        )
        assert resp.status_code == 502
        assert (
            resp.get_json()["error"]["code"] == "notification_failed"
        )


# =====================================================================
# GET /<id>/notifications — historico
# =====================================================================


class TestListNotificationsEndpoint:
    def test_list_returns_records(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.pharmacovigilance_service.list_notifications_for_event",
            lambda eid, *, tenant_id: [
                _make_notification(adverse_event_id=eid, id=10),
                _make_notification(adverse_event_id=eid, id=11),
            ],
        )
        resp = client.get(
            "/api/v1/pharmacovigilance/adverse-events/5/notifications"
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]["notifications"]) == 2
        assert body["meta"]["count"] == 2

    def test_list_returns_404(self, client, monkeypatch):
        def boom(*a, **kw):
            raise AdverseEventNotFoundError("evento nao encontrado")

        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.pharmacovigilance_service.list_notifications_for_event",
            boom,
        )
        resp = client.get(
            "/api/v1/pharmacovigilance/adverse-events/999/notifications"
        )
        assert resp.status_code == 404


# =====================================================================
# GET /dashboard
# =====================================================================


class TestDashboardEndpoint:
    def test_dashboard_returns_summary(self, client, monkeypatch):
        summary = DashboardSummary(
            tenant_id=TENANT_ID,
            period_days=30,
            generated_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
            total_events=5,
            events_by_severity={"mild": 2, "severe": 3},
            events_requiring_notification=3,
            notifications_by_target={"internal_only": 2},
        )
        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.pharmacovigilance_service.dashboard_summary",
            lambda tid, *, period_days=30: summary,
        )
        resp = client.get("/api/v1/pharmacovigilance/dashboard")
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["total_events"] == 5
        assert body["events_requiring_notification"] == 3
        assert body["events_by_severity"]["severe"] == 3
        assert body["notifications_by_target"]["internal_only"] == 2

    def test_dashboard_passes_period_days(self, client, monkeypatch):
        captured: dict[str, Any] = {}
        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.pharmacovigilance_service.dashboard_summary",
            lambda tid, *, period_days=30: captured.update(
                {"tid": tid, "period_days": period_days}
            ) or DashboardSummary(
                tenant_id=tid, period_days=period_days,
                generated_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
                total_events=0, events_by_severity={},
                events_requiring_notification=0,
                notifications_by_target={},
            ),
        )
        client.get("/api/v1/pharmacovigilance/dashboard?period_days=90")
        assert captured["period_days"] == 90

    def test_dashboard_clamps_period_days(self, client, monkeypatch):
        captured: dict[str, Any] = {}
        monkeypatch.setattr(
            "src.web.routes.pharmacovigilance.pharmacovigilance_service.dashboard_summary",
            lambda tid, *, period_days=30: captured.update(
                {"period_days": period_days}
            ) or DashboardSummary(
                tenant_id=tid, period_days=period_days,
                generated_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
                total_events=0, events_by_severity={},
                events_requiring_notification=0,
                notifications_by_target={},
            ),
        )
        client.get("/api/v1/pharmacovigilance/dashboard?period_days=99999")
        assert captured["period_days"] == 365
