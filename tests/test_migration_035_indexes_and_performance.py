"""
Tests da migration 035 — Indexes e performance (F6.1 do docs/BACKLOG_SCC.md).

Cobertura em duas camadas:

  1. Static analysis do SQL — todos os indexes esperados estao presentes,
     usam IF NOT EXISTS, partial indexes tem WHERE clause correto, etc.
  2. Integration: aplica em DB real e valida via pg_indexes que cada
     index foi criado com a definicao esperada.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.infra.database import db_cursor


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION_035 = MIGRATIONS_DIR / "035_indexes_and_performance.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql_035() -> str:
    assert MIGRATION_035.exists(), f"migration ausente: {MIGRATION_035}"
    content = _read(MIGRATION_035)
    assert content.strip(), "migration 035 esta vazia"
    return content


# ===========================================================================
# Static analysis
# ===========================================================================


class TestStructure:
    def test_has_header(self, sql_035: str) -> None:
        assert "Migration 035" in sql_035
        assert "F6.1" in sql_035 or "BACKLOG_SCC" in sql_035

    def test_no_manual_schema_migrations_insert(self, sql_035: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql_035
        assert "UPDATE schema_migrations" not in sql_035

    def test_renumbering_is_explained(self, sql_035: str) -> None:
        # Slot original do BACKLOG era 034; 034 foi tomado por
        # review_workflows. Esta migration ocupa o 035 e o cabecalho
        # precisa explicar a colisao.
        assert "034" in sql_035
        assert "035" in sql_035


# ===========================================================================
# Indexes esperados
# ===========================================================================


class TestExpectedIndexes:
    @pytest.mark.parametrize(
        "index_name",
        [
            "idx_trace_tenant_occurred",
            "idx_trace_tenant_type_occurred",
            "idx_ae_tenant_reported",
            "idx_ae_tenant_severity_reported",
            "idx_pv_notif_pending",
            "idx_followup_responded",
            "idx_treatment_plans_clinic_status_created",
            "idx_ai_audit_logs_clinic_created",
            "idx_anchors_pending",
            "idx_siv_indicator_period_desc",
            "idx_symptom_diary_clinic_created",
        ],
    )
    def test_index_declared(self, sql_035: str, index_name: str) -> None:
        assert f"CREATE INDEX IF NOT EXISTS {index_name}" in sql_035


class TestPartialIndexes:
    def test_pv_notif_pending_filters_response_null(self, sql_035: str) -> None:
        # O index so cobre notificacoes pendentes (sem resposta)
        assert "idx_pv_notif_pending" in sql_035
        # Verifica que a clausula WHERE response_received_at IS NULL
        # aparece logo depois do index name (na mesma definicao)
        idx = sql_035.find("idx_pv_notif_pending")
        # Procura WHERE response_received_at IS NULL nos proximos 300 chars
        following = sql_035[idx : idx + 400]
        assert "WHERE response_received_at IS NULL" in following

    def test_followup_responded_filters_responded_not_null(self, sql_035: str) -> None:
        idx = sql_035.find("idx_followup_responded")
        following = sql_035[idx : idx + 400]
        assert "WHERE responded_at IS NOT NULL" in following

    def test_anchors_pending_filters_status(self, sql_035: str) -> None:
        idx = sql_035.find("idx_anchors_pending")
        following = sql_035[idx : idx + 400]
        assert "WHERE verification_status = 'pending'" in following


class TestOrdering:
    def test_trace_indexes_are_desc(self, sql_035: str) -> None:
        # Dashboards mais recentes -> ordering DESC em occurred_at
        for needle in [
            "(tenant_id, occurred_at DESC)",
            "(tenant_id, event_type, occurred_at DESC)",
        ]:
            assert needle in sql_035

    def test_ae_indexes_are_desc(self, sql_035: str) -> None:
        for needle in [
            "(tenant_id, reported_at DESC)",
            "(tenant_id, severity, reported_at DESC)",
        ]:
            assert needle in sql_035

    def test_treatment_plans_index_orders_created_desc(self, sql_035: str) -> None:
        assert "(clinic_id, status, created_at DESC)" in sql_035

    def test_siv_index_orders_period_desc(self, sql_035: str) -> None:
        assert "(indicator_id, period_start DESC)" in sql_035


class TestIdempotency:
    def test_all_creates_use_if_not_exists(self, sql_035: str) -> None:
        code_lines = [
            line for line in sql_035.splitlines()
            if not line.lstrip().startswith("--")
        ]
        code = "\n".join(code_lines)
        assert code.count("CREATE INDEX") == code.count("CREATE INDEX IF NOT EXISTS")
        assert (
            code.count("CREATE UNIQUE INDEX")
            == code.count("CREATE UNIQUE INDEX IF NOT EXISTS")
        )


# ===========================================================================
# Integration — verifica que os indexes existem no DB apos a migration
# ===========================================================================


def _db_reachable() -> bool:
    try:
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not _db_reachable(), reason="DB local nao alcancavel")
class TestIndexesPresentInDb:
    """Assume migration 035 ja foi aplicada (run_migrations cobre)."""

    @pytest.mark.parametrize(
        "table, index_name",
        [
            ("traceability_events", "idx_trace_tenant_occurred"),
            ("traceability_events", "idx_trace_tenant_type_occurred"),
            ("adverse_events", "idx_ae_tenant_reported"),
            ("adverse_events", "idx_ae_tenant_severity_reported"),
            ("pharmacovigilance_notifications", "idx_pv_notif_pending"),
            ("scheduled_followups", "idx_followup_responded"),
            ("treatment_plans", "idx_treatment_plans_clinic_status_created"),
            ("ai_audit_logs", "idx_ai_audit_logs_clinic_created"),
            ("blockchain_anchors", "idx_anchors_pending"),
            ("sandbox_indicator_values", "idx_siv_indicator_period_desc"),
            ("symptom_diary", "idx_symptom_diary_clinic_created"),
        ],
    )
    def test_index_exists(self, table: str, index_name: str) -> None:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                """
                SELECT indexdef FROM pg_indexes
                 WHERE schemaname = 'public'
                   AND tablename = %s
                   AND indexname = %s
                """,
                (table, index_name),
            )
            row = cur.fetchone()
        assert row is not None, f"index {index_name} ausente em {table}"

    def test_pv_notif_pending_is_partial(self) -> None:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT indexdef FROM pg_indexes "
                "WHERE indexname = 'idx_pv_notif_pending'"
            )
            row = cur.fetchone()
        assert row is not None
        assert "response_received_at IS NULL" in row["indexdef"]

    def test_followup_responded_is_partial(self) -> None:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT indexdef FROM pg_indexes "
                "WHERE indexname = 'idx_followup_responded'"
            )
            row = cur.fetchone()
        assert row is not None
        assert "responded_at IS NOT NULL" in row["indexdef"]

    def test_anchors_pending_is_partial(self) -> None:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT indexdef FROM pg_indexes "
                "WHERE indexname = 'idx_anchors_pending'"
            )
            row = cur.fetchone()
        assert row is not None
        # Postgres normaliza para ((verification_status)::text = 'pending'::text)
        # ao reler de pg_indexes — aceitamos qualquer forma equivalente.
        idef = row["indexdef"]
        assert "verification_status" in idef
        assert "'pending'" in idef
        assert "WHERE" in idef
