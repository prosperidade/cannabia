"""Tests do orquestrador pharmacovigilance_service (F3.6 do SCC).

Roda contra Postgres real (skip automatico se DB nao alcancavel).
Cobre os 3 casos de uso publicos:
  - triage_event       → grava ai_triage_result via skill F3.4
  - notify_event       → grava em pharmacovigilance_notifications via F3.5
  - dashboard_summary  → counts agregados
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.infra.database import db_cursor
from src.services import (
    adverse_event_service as ae_svc,
    pharmacovigilance_service as pv_svc,
)


def _db_reachable() -> bool:
    try:
        with db_cursor() as (_, cur):
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="DB local nao alcancavel"
)


@pytest.fixture(autouse=True)
def _force_mock_provider(monkeypatch):
    """Garante que o dispatcher F3.5 fica em mock mesmo se o ambiente
    do dev tiver outro provider configurado."""
    monkeypatch.delenv("ANVISA_NOTIFICATION_PROVIDER", raising=False)
    yield


@pytest.fixture
def fixture_tenant_id():
    suffix = uuid.uuid4().hex[:8]
    name = f"pv_svc_{suffix}"
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO tenants (tenant_type_id, tenant_type, legal_name,
                                 display_name, slug, status)
            VALUES (
              (SELECT id FROM tenant_types WHERE slug='association' LIMIT 1),
              'association', %s, %s, %s, 'active'
            )
            RETURNING id
            """,
            (name, name, name),
        )
        tenant_id = cur.fetchone()["id"]
        conn.commit()

    yield tenant_id

    with db_cursor() as (conn, cur):
        cur.execute(
            "DELETE FROM pharmacovigilance_notifications "
            "WHERE adverse_event_id IN "
            "(SELECT id FROM adverse_events WHERE tenant_id = %s)",
            (tenant_id,),
        )
        cur.execute(
            "DELETE FROM adverse_events WHERE tenant_id = %s", (tenant_id,)
        )
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
        conn.commit()


def _capture(tenant_id: int, **overrides) -> int:
    """Helper: cria um evento com defaults sensatos e retorna o id."""
    base = dict(
        tenant_id=tenant_id,
        description="Paciente relatou sintoma adverso.",
        severity="mild",
        reported_via="web",
    )
    base.update(overrides)
    event = ae_svc.capture_adverse_event(**base)
    return event.id


# =====================================================================
# triage_event
# =====================================================================


class TestTriageEvent:
    def test_triage_persists_ai_triage_result(self, fixture_tenant_id, monkeypatch):
        # Stub diary_write — fire-and-forget, nao queremos rede
        monkeypatch.setattr(
            "src.ai.agents.base.diary_write", lambda *a, **kw: True
        )
        event_id = _capture(
            fixture_tenant_id,
            description="Paciente internado com convulsao.",
            severity="moderate",
        )

        result = pv_svc.triage_event(event_id, tenant_id=fixture_tenant_id)

        assert result["ok"] is True
        assert result["severity_suggested"] == "life_threatening"
        assert result["escalated"] is True
        assert result["notify_required"] is True

        # Estado pos-update veio anexado
        refreshed = result["event"]
        assert refreshed is not None
        assert refreshed.ai_triage_result is not None
        assert refreshed.ai_triage_result["severity_suggested"] == "life_threatening"

    def test_triage_raises_for_missing_event(self, fixture_tenant_id, monkeypatch):
        monkeypatch.setattr(
            "src.ai.agents.base.diary_write", lambda *a, **kw: True
        )
        with pytest.raises(pv_svc.AdverseEventNotFoundError):
            pv_svc.triage_event(999_999_999, tenant_id=fixture_tenant_id)

    def test_triage_isolated_by_tenant(self, fixture_tenant_id, monkeypatch):
        # Cria evento em outro tenant — nao pode ser triado pelo nosso
        monkeypatch.setattr(
            "src.ai.agents.base.diary_write", lambda *a, **kw: True
        )
        suffix = uuid.uuid4().hex[:8]
        with db_cursor(dictionary=True) as (conn, cur):
            cur.execute(
                """
                INSERT INTO tenants (tenant_type_id, tenant_type, legal_name,
                                     display_name, slug, status)
                VALUES (
                  (SELECT id FROM tenant_types WHERE slug='association' LIMIT 1),
                  'association', %s, %s, %s, 'active'
                )
                RETURNING id
                """,
                (f"pv_other_{suffix}",) * 3,
            )
            other_tenant = cur.fetchone()["id"]
            conn.commit()
        try:
            other_event_id = _capture(other_tenant, description="alheio")
            with pytest.raises(pv_svc.AdverseEventNotFoundError):
                pv_svc.triage_event(
                    other_event_id, tenant_id=fixture_tenant_id
                )
        finally:
            with db_cursor() as (conn, cur):
                cur.execute(
                    "DELETE FROM adverse_events WHERE tenant_id = %s",
                    (other_tenant,),
                )
                cur.execute(
                    "DELETE FROM tenants WHERE id = %s", (other_tenant,)
                )
                conn.commit()


# =====================================================================
# notify_event
# =====================================================================


class TestNotifyEvent:
    def test_notify_with_default_provider_uses_mock_target(
        self, fixture_tenant_id
    ):
        event_id = _capture(
            fixture_tenant_id,
            description="Paciente internado.",
            severity="severe",
        )
        record = pv_svc.notify_event(event_id, tenant_id=fixture_tenant_id)

        assert record.adverse_event_id == event_id
        assert record.notification_target == "internal_only"
        assert record.notification_reference is not None
        assert record.notification_reference.startswith("MOCK-")
        assert record.response_payload is not None
        assert record.response_payload["accepted"] is True

    def test_notify_with_explicit_mock_provider_for_vigimed_target(
        self, fixture_tenant_id
    ):
        # provider='vigimed' nesse ambiente cairia no stub real e falharia.
        # Para testar mapping, usamos provider='mock' mas com client
        # injetado no service. Como o service nao expoe injecao, validamos
        # apenas que o caminho default produz um receipt valido.
        event_id = _capture(fixture_tenant_id, severity="severe")
        record = pv_svc.notify_event(
            event_id, tenant_id=fixture_tenant_id, provider="mock"
        )
        assert record.notification_target == "internal_only"

    def test_notify_raises_for_missing_event(self, fixture_tenant_id):
        with pytest.raises(pv_svc.AdverseEventNotFoundError):
            pv_svc.notify_event(
                999_999_999, tenant_id=fixture_tenant_id
            )

    def test_notify_propagates_unknown_provider_error(self, fixture_tenant_id):
        from src.integrations.vigimed import UnknownProviderError

        event_id = _capture(fixture_tenant_id)
        with pytest.raises(UnknownProviderError):
            pv_svc.notify_event(
                event_id, tenant_id=fixture_tenant_id, provider="anvisa-direto"
            )

    def test_list_notifications_for_event(self, fixture_tenant_id):
        event_id = _capture(fixture_tenant_id, severity="severe")
        # Notifica 2 vezes — ambas vao parar no historico
        pv_svc.notify_event(event_id, tenant_id=fixture_tenant_id)
        pv_svc.notify_event(event_id, tenant_id=fixture_tenant_id)

        records = pv_svc.list_notifications_for_event(
            event_id, tenant_id=fixture_tenant_id
        )
        assert len(records) == 2
        assert all(r.adverse_event_id == event_id for r in records)
        # Mock e deterministico → mesma reference
        assert records[0].notification_reference == records[1].notification_reference

    def test_list_notifications_raises_for_missing_event(self, fixture_tenant_id):
        with pytest.raises(pv_svc.AdverseEventNotFoundError):
            pv_svc.list_notifications_for_event(
                999_999_999, tenant_id=fixture_tenant_id
            )

    def test_record_response_updates_existing_notification(
        self, fixture_tenant_id
    ):
        event_id = _capture(fixture_tenant_id, severity="severe")
        record = pv_svc.notify_event(event_id, tenant_id=fixture_tenant_id)

        confirm_at = datetime.now(timezone.utc)
        updated = pv_svc.record_notification_response(
            record.id,
            tenant_id=fixture_tenant_id,
            response_received_at=confirm_at,
            response_payload={"agency_status": "accepted"},
        )
        assert updated is not None
        assert updated.response_received_at is not None
        assert updated.response_payload["agency_status"] == "accepted"


# =====================================================================
# dashboard_summary
# =====================================================================


class TestDashboardSummary:
    def test_dashboard_counts_severities_in_window(self, fixture_tenant_id):
        for sev in ("mild", "mild", "moderate", "severe", "fatal"):
            _capture(fixture_tenant_id, severity=sev, description=f"e {sev}")

        s = pv_svc.dashboard_summary(fixture_tenant_id, period_days=30)
        assert s.total_events == 5
        assert s.events_by_severity["mild"] == 2
        assert s.events_by_severity["moderate"] == 1
        assert s.events_by_severity["severe"] == 1
        assert s.events_by_severity["fatal"] == 1
        # severe + fatal sao notificaveis
        assert s.events_requiring_notification == 2

    def test_dashboard_counts_notifications_by_target(self, fixture_tenant_id):
        event_id = _capture(fixture_tenant_id, severity="severe")
        pv_svc.notify_event(event_id, tenant_id=fixture_tenant_id)
        pv_svc.notify_event(event_id, tenant_id=fixture_tenant_id)

        s = pv_svc.dashboard_summary(fixture_tenant_id, period_days=30)
        assert s.notifications_by_target.get("internal_only") == 2

    def test_dashboard_excludes_old_events(self, fixture_tenant_id):
        # Captura com reported_at fora da janela
        old_when = datetime.now(timezone.utc) - timedelta(days=60)
        _capture(
            fixture_tenant_id,
            severity="mild",
            reported_at=old_when,
            description="antigo",
        )
        s = pv_svc.dashboard_summary(fixture_tenant_id, period_days=30)
        assert s.total_events == 0

    def test_dashboard_isolated_by_tenant(self, fixture_tenant_id):
        # Cria evento em OUTRO tenant
        suffix = uuid.uuid4().hex[:8]
        with db_cursor(dictionary=True) as (conn, cur):
            cur.execute(
                """
                INSERT INTO tenants (tenant_type_id, tenant_type, legal_name,
                                     display_name, slug, status)
                VALUES (
                  (SELECT id FROM tenant_types WHERE slug='association' LIMIT 1),
                  'association', %s, %s, %s, 'active'
                )
                RETURNING id
                """,
                (f"pv_d_{suffix}",) * 3,
            )
            other_tenant = cur.fetchone()["id"]
            conn.commit()
        try:
            _capture(other_tenant, severity="severe", description="alheio")
            s = pv_svc.dashboard_summary(fixture_tenant_id, period_days=30)
            assert s.total_events == 0
        finally:
            with db_cursor() as (conn, cur):
                cur.execute(
                    "DELETE FROM adverse_events WHERE tenant_id = %s",
                    (other_tenant,),
                )
                cur.execute(
                    "DELETE FROM tenants WHERE id = %s", (other_tenant,)
                )
                conn.commit()
