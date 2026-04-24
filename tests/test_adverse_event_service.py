"""
Tests do adverse_event_service (F3.3 do docs/BACKLOG_SCC.md).

Duas camadas:
  1. Validacao pura (sem DB): payload invalido levanta
     AdverseEventValidationError.
  2. Integracao (DB real): captura, listagem, filtros, updates,
     isolamento por tenant.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.infra.database import db_cursor
from src.services import adverse_event_service as svc
from src.services.adverse_event_service import (
    AdverseEventValidationError,
    NOTIFIABLE_SEVERITIES,
)


# ===========================================================================
# Camada 1 — validacao pura (sem DB)
# ===========================================================================


class TestValidation:
    def test_rejects_empty_description(self) -> None:
        with pytest.raises(AdverseEventValidationError, match="description"):
            svc.capture_adverse_event(
                tenant_id=1,
                description="   ",
                severity="mild",
                reported_via="whatsapp",
            )

    def test_rejects_invalid_severity(self) -> None:
        with pytest.raises(AdverseEventValidationError, match="severity"):
            svc.capture_adverse_event(
                tenant_id=1,
                description="dor de cabeca leve",
                severity="catastrophic",
                reported_via="whatsapp",
            )

    def test_rejects_invalid_reported_via(self) -> None:
        with pytest.raises(AdverseEventValidationError, match="reported_via"):
            svc.capture_adverse_event(
                tenant_id=1,
                description="dor de cabeca leve",
                severity="mild",
                reported_via="carrier_pigeon",
            )

    def test_rejects_onset_after_report(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(AdverseEventValidationError, match="onset"):
            svc.capture_adverse_event(
                tenant_id=1,
                description="nausea",
                severity="mild",
                reported_via="web",
                reported_at=now - timedelta(hours=1),
                event_onset_at=now,
            )

    def test_list_rejects_invalid_severity_filter(self) -> None:
        with pytest.raises(AdverseEventValidationError, match="severity"):
            svc.list_events(tenant_id=1, severity="catastrophic")

    def test_list_rejects_invalid_reported_via_filter(self) -> None:
        with pytest.raises(AdverseEventValidationError, match="reported_via"):
            svc.list_events(tenant_id=1, reported_via="carrier_pigeon")

    def test_record_triage_rejects_non_dict(self) -> None:
        with pytest.raises(AdverseEventValidationError, match="dict"):
            svc.record_triage_result(
                event_id=1,
                tenant_id=1,
                ai_triage_result="severity=high",  # type: ignore[arg-type]
            )

    def test_set_assessment_rejects_empty(self) -> None:
        with pytest.raises(AdverseEventValidationError):
            svc.set_clinical_assessment(
                event_id=1, tenant_id=1, assessment=""
            )

    def test_set_outcome_rejects_invalid(self) -> None:
        with pytest.raises(AdverseEventValidationError, match="outcome"):
            svc.set_outcome(event_id=1, tenant_id=1, outcome="gone_forever")

    def test_notifiable_severities_match_whitelist(self) -> None:
        # Garante que a lista de severidades notificaveis nao drifta
        assert NOTIFIABLE_SEVERITIES == frozenset(
            {"severe", "life_threatening", "fatal"}
        )


# ===========================================================================
# Camada 2 — integracao com DB real
# ===========================================================================


def _db_reachable() -> bool:
    try:
        with db_cursor() as (_, cur):
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False


integration = pytest.mark.skipif(
    not _db_reachable(), reason="DB local nao alcancavel"
)


@pytest.fixture
def fixture_tenant_id() -> int:
    suffix = uuid.uuid4().hex[:8]
    name = f"ae_test_{suffix}"
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
        cur.execute(
            "DELETE FROM association_members WHERE tenant_id = %s", (tenant_id,)
        )
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
        conn.commit()


@pytest.fixture
def fixture_member_id(fixture_tenant_id: int) -> int:
    """Cria um association_member para vincular aos eventos."""
    suffix = uuid.uuid4().hex[:8]
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO association_members (
              tenant_id, membership_number, membership_status, joined_at
            )
            VALUES (%s, %s, 'active', CURRENT_DATE)
            RETURNING id
            """,
            (fixture_tenant_id, f"MB-{suffix}"),
        )
        member_id = cur.fetchone()["id"]
        conn.commit()
    return member_id


@integration
class TestCapture:
    def test_capture_minimal_fields(self, fixture_tenant_id: int) -> None:
        event = svc.capture_adverse_event(
            tenant_id=fixture_tenant_id,
            description="Paciente relatou dor de cabeca leve",
            severity="mild",
            reported_via="whatsapp",
        )

        assert event.id > 0
        assert event.tenant_id == fixture_tenant_id
        assert event.severity == "mild"
        assert event.reported_via == "whatsapp"
        assert event.description == "Paciente relatou dor de cabeca leve"
        # reported_at default = now, aware em UTC
        assert event.reported_at.tzinfo is not None
        delta = datetime.now(timezone.utc) - event.reported_at
        assert abs(delta.total_seconds()) < 60

        # Campos opcionais nulos
        assert event.member_id is None
        assert event.preparation_id is None
        assert event.event_onset_at is None
        assert event.ai_triage_result is None
        assert event.triaged_by is None
        assert event.clinical_assessment is None
        assert event.outcome is None

        # Mild nao e notificavel
        assert event.requires_regulatory_notification is False

    def test_capture_with_member_and_onset(
        self, fixture_tenant_id: int, fixture_member_id: int
    ) -> None:
        onset = datetime.now(timezone.utc) - timedelta(days=2)
        reported = datetime.now(timezone.utc) - timedelta(days=1)
        event = svc.capture_adverse_event(
            tenant_id=fixture_tenant_id,
            member_id=fixture_member_id,
            description="Nausea intensa apos dose",
            severity="severe",
            reported_via="consultation",
            reported_at=reported,
            event_onset_at=onset,
        )

        assert event.member_id == fixture_member_id
        assert event.event_onset_at == onset
        assert event.reported_at == reported
        # severe entra na whitelist de notificacao regulatoria
        assert event.requires_regulatory_notification is True

    def test_capture_strips_description(self, fixture_tenant_id: int) -> None:
        event = svc.capture_adverse_event(
            tenant_id=fixture_tenant_id,
            description="   taquicardia leve   ",
            severity="mild",
            reported_via="phone",
        )
        assert event.description == "taquicardia leve"


@integration
class TestQuery:
    def test_get_event_returns_none_for_missing(
        self, fixture_tenant_id: int
    ) -> None:
        assert svc.get_event(999_999_999, tenant_id=fixture_tenant_id) is None

    def test_get_event_roundtrip(self, fixture_tenant_id: int) -> None:
        created = svc.capture_adverse_event(
            tenant_id=fixture_tenant_id,
            description="tontura breve",
            severity="mild",
            reported_via="web",
        )
        fetched = svc.get_event(created.id, tenant_id=fixture_tenant_id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.description == "tontura breve"

    def test_tenant_isolation(self, fixture_tenant_id: int) -> None:
        # Evento em tenant A nao deve ser visivel de tenant B
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
                (f"ae_other_{suffix}",) * 3,
            )
            other_tenant = cur.fetchone()["id"]
            conn.commit()

        try:
            created = svc.capture_adverse_event(
                tenant_id=fixture_tenant_id,
                description="sonolencia diurna",
                severity="mild",
                reported_via="whatsapp",
            )
            # Cross-tenant get deve devolver None
            assert svc.get_event(created.id, tenant_id=other_tenant) is None
            # Cross-tenant list nao traz o evento
            other_events = svc.list_events(other_tenant)
            assert all(e.id != created.id for e in other_events)
        finally:
            with db_cursor() as (conn, cur):
                cur.execute(
                    "DELETE FROM tenants WHERE id = %s", (other_tenant,)
                )
                conn.commit()


@integration
class TestListFilters:
    def test_filter_by_severity(
        self, fixture_tenant_id: int, fixture_member_id: int
    ) -> None:
        for sev, desc in [
            ("mild", "leve"),
            ("moderate", "media"),
            ("severe", "grave"),
        ]:
            svc.capture_adverse_event(
                tenant_id=fixture_tenant_id,
                member_id=fixture_member_id,
                description=desc,
                severity=sev,
                reported_via="web",
            )

        severe_only = svc.list_events(fixture_tenant_id, severity="severe")
        assert len(severe_only) == 1
        assert severe_only[0].description == "grave"

    def test_filter_by_reported_via(self, fixture_tenant_id: int) -> None:
        svc.capture_adverse_event(
            tenant_id=fixture_tenant_id,
            description="via web",
            severity="mild",
            reported_via="web",
        )
        svc.capture_adverse_event(
            tenant_id=fixture_tenant_id,
            description="via whatsapp",
            severity="mild",
            reported_via="whatsapp",
        )
        wpp_only = svc.list_events(fixture_tenant_id, reported_via="whatsapp")
        assert len(wpp_only) == 1
        assert wpp_only[0].reported_via == "whatsapp"

    def test_filter_by_member(
        self, fixture_tenant_id: int, fixture_member_id: int
    ) -> None:
        svc.capture_adverse_event(
            tenant_id=fixture_tenant_id,
            member_id=fixture_member_id,
            description="com membro",
            severity="mild",
            reported_via="consultation",
        )
        svc.capture_adverse_event(
            tenant_id=fixture_tenant_id,
            description="publico anonimo",
            severity="mild",
            reported_via="whatsapp",
        )
        member_only = svc.list_events(
            fixture_tenant_id, member_id=fixture_member_id
        )
        assert len(member_only) == 1
        assert member_only[0].member_id == fixture_member_id

    def test_filter_has_triage(self, fixture_tenant_id: int) -> None:
        a = svc.capture_adverse_event(
            tenant_id=fixture_tenant_id,
            description="sem triagem",
            severity="mild",
            reported_via="web",
        )
        b = svc.capture_adverse_event(
            tenant_id=fixture_tenant_id,
            description="com triagem",
            severity="moderate",
            reported_via="web",
        )
        svc.record_triage_result(
            b.id,
            tenant_id=fixture_tenant_id,
            ai_triage_result={"severity_suggested": "moderate", "notify_required": False},
        )

        with_triage = svc.list_events(fixture_tenant_id, has_triage=True)
        without = svc.list_events(fixture_tenant_id, has_triage=False)
        with_ids = {e.id for e in with_triage}
        without_ids = {e.id for e in without}
        assert b.id in with_ids and a.id not in with_ids
        assert a.id in without_ids and b.id not in without_ids

    def test_filter_by_window(self, fixture_tenant_id: int) -> None:
        now = datetime.now(timezone.utc)
        old = svc.capture_adverse_event(
            tenant_id=fixture_tenant_id,
            description="antigo",
            severity="mild",
            reported_via="web",
            reported_at=now - timedelta(days=30),
        )
        recent = svc.capture_adverse_event(
            tenant_id=fixture_tenant_id,
            description="recente",
            severity="mild",
            reported_via="web",
            reported_at=now - timedelta(days=1),
        )

        window = svc.list_events(
            fixture_tenant_id, since=now - timedelta(days=7)
        )
        ids = {e.id for e in window}
        assert recent.id in ids
        assert old.id not in ids

    def test_count_by_severity(self, fixture_tenant_id: int) -> None:
        for sev in ["mild", "mild", "moderate", "severe"]:
            svc.capture_adverse_event(
                tenant_id=fixture_tenant_id,
                description=f"evento {sev}",
                severity=sev,
                reported_via="web",
            )
        counts = svc.count_by_severity(fixture_tenant_id)
        assert counts.get("mild") == 2
        assert counts.get("moderate") == 1
        assert counts.get("severe") == 1
        # Severidades nao reportadas nao aparecem
        assert "fatal" not in counts

    def test_list_ordered_reported_desc(self, fixture_tenant_id: int) -> None:
        now = datetime.now(timezone.utc)
        for delta, desc in [(5, "mais antigo"), (1, "mais recente"), (3, "meio")]:
            svc.capture_adverse_event(
                tenant_id=fixture_tenant_id,
                description=desc,
                severity="mild",
                reported_via="web",
                reported_at=now - timedelta(days=delta),
            )
        events = svc.list_events(fixture_tenant_id)
        descs = [e.description for e in events]
        assert descs == ["mais recente", "meio", "mais antigo"]


@integration
class TestUpdates:
    def test_record_triage_result(self, fixture_tenant_id: int) -> None:
        created = svc.capture_adverse_event(
            tenant_id=fixture_tenant_id,
            description="sonolencia excessiva",
            severity="mild",
            reported_via="whatsapp",
        )
        payload = {
            "severity_suggested": "moderate",
            "notify_required": False,
            "reasoning": "sintoma conhecido do CBD em dose inicial",
            "model_version": "regulatorio-v1",
        }
        updated = svc.record_triage_result(
            created.id, tenant_id=fixture_tenant_id, ai_triage_result=payload
        )
        assert updated is not None
        assert updated.ai_triage_result == payload
        assert updated.updated_at >= created.updated_at

    def test_record_triage_returns_none_for_missing(
        self, fixture_tenant_id: int
    ) -> None:
        result = svc.record_triage_result(
            999_999_999,
            tenant_id=fixture_tenant_id,
            ai_triage_result={"x": 1},
        )
        assert result is None

    def test_set_clinical_assessment(self, fixture_tenant_id: int) -> None:
        created = svc.capture_adverse_event(
            tenant_id=fixture_tenant_id,
            description="rash cutaneo",
            severity="moderate",
            reported_via="consultation",
        )
        updated = svc.set_clinical_assessment(
            created.id,
            tenant_id=fixture_tenant_id,
            assessment="  Reacao dermatologica provavelmente auto-limitada.  ",
        )
        assert updated is not None
        assert updated.clinical_assessment == (
            "Reacao dermatologica provavelmente auto-limitada."
        )

    def test_set_outcome(self, fixture_tenant_id: int) -> None:
        created = svc.capture_adverse_event(
            tenant_id=fixture_tenant_id,
            description="insonia",
            severity="mild",
            reported_via="web",
        )
        updated = svc.set_outcome(
            created.id, tenant_id=fixture_tenant_id, outcome="resolved"
        )
        assert updated is not None
        assert updated.outcome == "resolved"

    def test_set_outcome_returns_none_for_missing(
        self, fixture_tenant_id: int
    ) -> None:
        result = svc.set_outcome(
            999_999_999, tenant_id=fixture_tenant_id, outcome="resolved"
        )
        assert result is None


@integration
class TestNotifiableProperty:
    @pytest.mark.parametrize(
        "severity,expected",
        [
            ("mild", False),
            ("moderate", False),
            ("severe", True),
            ("life_threatening", True),
            ("fatal", True),
        ],
    )
    def test_requires_regulatory_notification(
        self,
        fixture_tenant_id: int,
        severity: str,
        expected: bool,
    ) -> None:
        event = svc.capture_adverse_event(
            tenant_id=fixture_tenant_id,
            description=f"evento {severity}",
            severity=severity,
            reported_via="web",
        )
        assert event.requires_regulatory_notification is expected
