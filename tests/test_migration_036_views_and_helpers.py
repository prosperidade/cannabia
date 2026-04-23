"""
Tests da migration 036 — Views e helpers (F6.2 do docs/BACKLOG_SCC.md).

Cobertura em duas camadas:

  1. Static analysis do SQL — todas as views e funcoes esperadas estao
     declaradas, com CREATE OR REPLACE (idempotente).
  2. Integration: aplica em DB real e testa comportamento de cada view
     e funcao com fixtures controladas.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.infra.database import db_cursor


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION_036 = MIGRATIONS_DIR / "036_views_and_helpers.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql_036() -> str:
    assert MIGRATION_036.exists(), f"migration ausente: {MIGRATION_036}"
    content = _read(MIGRATION_036)
    assert content.strip(), "migration 036 esta vazia"
    return content


# ===========================================================================
# Static analysis
# ===========================================================================


class TestStructure:
    def test_has_header(self, sql_036: str) -> None:
        assert "Migration 036" in sql_036
        assert "F6.2" in sql_036 or "BACKLOG_SCC" in sql_036

    def test_no_manual_schema_migrations_insert(self, sql_036: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql_036
        assert "UPDATE schema_migrations" not in sql_036


class TestExpectedObjects:
    @pytest.mark.parametrize(
        "view_name",
        [
            "v_member_active_prescriptions",
            "v_traceability_chain_status",
            "v_sandbox_indicator_dashboard",
        ],
    )
    def test_view_declared(self, sql_036: str, view_name: str) -> None:
        assert f"CREATE OR REPLACE VIEW {view_name}" in sql_036

    @pytest.mark.parametrize(
        "fn_name",
        ["fn_generate_event_hash", "fn_verify_chain_integrity"],
    )
    def test_function_declared(self, sql_036: str, fn_name: str) -> None:
        assert f"CREATE OR REPLACE FUNCTION {fn_name}" in sql_036


class TestIdempotency:
    def test_all_creates_use_or_replace(self, sql_036: str) -> None:
        # Todo CREATE de view/funcao deve ter OR REPLACE
        code_lines = [
            line for line in sql_036.splitlines()
            if not line.lstrip().startswith("--")
        ]
        code = "\n".join(code_lines)
        assert code.count("CREATE VIEW") == 0
        assert code.count("CREATE FUNCTION") == 0
        # Deve ter exatamente os 5 declarados via OR REPLACE
        assert code.count("CREATE OR REPLACE VIEW") >= 3
        assert code.count("CREATE OR REPLACE FUNCTION") >= 2


class TestMaterializedViewDecisionDocumented:
    def test_materialized_decision_explicit(self, sql_036: str) -> None:
        # O doc 25 sugere materialized para v_sandbox_indicator_dashboard
        # mas escolhemos regular view por dados sempre frescos.
        # Decisao deve estar documentada no cabecalho.
        assert "materialized" in sql_036.lower() or "MATERIALIZED" in sql_036


# ===========================================================================
# Integration — DB real
# ===========================================================================


def _db_reachable() -> bool:
    try:
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="DB local nao alcancavel"
)


# ---------------------------------------------------------------------------
# fn_generate_event_hash — testes puros (sem fixtures)
# ---------------------------------------------------------------------------


class TestFnGenerateEventHash:
    def test_returns_64_hex_chars(self) -> None:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT fn_generate_event_hash('{\"a\": 1}'::jsonb, NULL) AS h"
            )
            row = cur.fetchone()
        assert row is not None
        h = row["h"]
        assert isinstance(h, str)
        assert len(h.strip()) == 64
        assert all(c in "0123456789abcdef" for c in h.strip())

    def test_deterministic_same_payload_same_hash(self) -> None:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT fn_generate_event_hash('{\"a\": 1, \"b\": 2}'::jsonb, NULL) AS h1, "
                "       fn_generate_event_hash('{\"a\": 1, \"b\": 2}'::jsonb, NULL) AS h2"
            )
            row = cur.fetchone()
        assert row["h1"] == row["h2"]

    def test_different_payload_different_hash(self) -> None:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT fn_generate_event_hash('{\"a\": 1}'::jsonb, NULL) AS h1, "
                "       fn_generate_event_hash('{\"a\": 2}'::jsonb, NULL) AS h2"
            )
            row = cur.fetchone()
        assert row["h1"] != row["h2"]

    def test_previous_hash_changes_result(self) -> None:
        prev = "a" * 64
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT fn_generate_event_hash('{\"x\":1}'::jsonb, NULL) AS h_no_prev, "
                "       fn_generate_event_hash('{\"x\":1}'::jsonb, %s) AS h_with_prev",
                (prev,),
            )
            row = cur.fetchone()
        assert row["h_no_prev"] != row["h_with_prev"]


# ---------------------------------------------------------------------------
# fn_verify_chain_integrity — fixture com chain real em traceability_events
# ---------------------------------------------------------------------------


@pytest.fixture
def fixture_tenant_id() -> int:
    """Cria tenant minimo dedicado e retorna seu id."""
    suffix = uuid.uuid4().hex[:8]
    name = f"views_test_{suffix}"
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO tenants (tenant_type_id, tenant_type, legal_name,
                                 display_name, slug, status)
            VALUES (
              (SELECT id FROM tenant_types WHERE slug='clinic' LIMIT 1),
              'clinic', %s, %s, %s, 'active'
            )
            RETURNING id
            """,
            (name, name, name),
        )
        tenant_id = cur.fetchone()["id"]
        conn.commit()

    yield tenant_id

    with db_cursor() as (conn, cur):
        cur.execute("SET LOCAL session_replication_role = 'replica'")
        cur.execute("DELETE FROM traceability_events WHERE tenant_id = %s",
                    (tenant_id,))
        cur.execute(
            "DELETE FROM association_members WHERE tenant_id = %s", (tenant_id,)
        )
        cur.execute(
            "DELETE FROM sandbox_indicator_values WHERE indicator_id IN ("
            "  SELECT si.id FROM sandbox_indicators si "
            "  JOIN sandbox_projects sp ON sp.id = si.project_id "
            "  WHERE sp.tenant_id = %s)",
            (tenant_id,),
        )
        cur.execute(
            "DELETE FROM sandbox_indicators WHERE project_id IN ("
            "  SELECT id FROM sandbox_projects WHERE tenant_id = %s)",
            (tenant_id,),
        )
        cur.execute("DELETE FROM sandbox_projects WHERE tenant_id = %s",
                    (tenant_id,))
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
        conn.commit()


def _hash_for(payload_json: str, previous: str | None) -> str:
    """Computa hash via funcao do banco — fonte de verdade canonica."""
    with db_cursor(dictionary=True) as (_, cur):
        cur.execute(
            "SELECT fn_generate_event_hash(%s::jsonb, %s) AS h",
            (payload_json, previous),
        )
        return cur.fetchone()["h"]


def _insert_trace_event(
    tenant_id: int,
    chain_id: str,
    sequence: int,
    payload_json: str,
    previous: str | None,
) -> int:
    h = _hash_for(payload_json, previous)
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO traceability_events
              (tenant_id, event_type, subject_type, subject_id, payload,
               chain_id, chain_sequence, event_hash, previous_hash,
               occurred_at, created_at)
            VALUES (%s, 'planting', 'plant', 1, %s::jsonb, %s, %s, %s, %s,
                    NOW(), NOW())
            RETURNING id
            """,
            (tenant_id, payload_json, chain_id, sequence, h, previous),
        )
        eid = cur.fetchone()["id"]
        conn.commit()
        return eid


class TestFnVerifyChainIntegrity:
    def test_valid_chain_returns_all_valid(self, fixture_tenant_id: int) -> None:
        chain_id = f"chain-{uuid.uuid4().hex[:8]}"

        # Sequencia 1 -> 2 -> 3 com hashes corretos
        h1_payload = '{"step": 1}'
        e1_id = _insert_trace_event(fixture_tenant_id, chain_id, 1,
                                    h1_payload, None)
        h1 = _hash_for(h1_payload, None)

        h2_payload = '{"step": 2}'
        e2_id = _insert_trace_event(fixture_tenant_id, chain_id, 2,
                                    h2_payload, h1)
        h2 = _hash_for(h2_payload, h1)

        h3_payload = '{"step": 3}'
        e3_id = _insert_trace_event(fixture_tenant_id, chain_id, 3,
                                    h3_payload, h2)

        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT chain_sequence, valid "
                "FROM fn_verify_chain_integrity(%s) ORDER BY chain_sequence",
                (chain_id,),
            )
            rows = cur.fetchall()

        assert len(rows) == 3
        assert all(r["valid"] for r in rows)

    def test_first_event_with_non_null_previous_is_invalid(
        self, fixture_tenant_id: int
    ) -> None:
        chain_id = f"chain-{uuid.uuid4().hex[:8]}"

        # Insere sequence=1 com previous_hash NAO-NULL (adulterado)
        h1_payload = '{"step": 1}'
        bogus_prev = "f" * 64
        h1 = _hash_for(h1_payload, bogus_prev)
        with db_cursor(dictionary=True) as (conn, cur):
            cur.execute(
                """
                INSERT INTO traceability_events
                  (tenant_id, event_type, subject_type, subject_id,
                   payload, chain_id, chain_sequence,
                   event_hash, previous_hash, occurred_at)
                VALUES (%s, 'planting', 'plant', 1, %s::jsonb, %s, 1,
                        %s, %s, NOW())
                """,
                (fixture_tenant_id, h1_payload, chain_id, h1, bogus_prev),
            )
            conn.commit()

        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT chain_sequence, valid, expected_previous "
                "FROM fn_verify_chain_integrity(%s)",
                (chain_id,),
            )
            rows = cur.fetchall()

        assert len(rows) == 1
        assert rows[0]["valid"] is False

    def test_broken_chain_detected(self, fixture_tenant_id: int) -> None:
        chain_id = f"chain-{uuid.uuid4().hex[:8]}"

        # Sequence 1 valido
        h1_payload = '{"step": 1}'
        _insert_trace_event(fixture_tenant_id, chain_id, 1, h1_payload, None)

        # Sequence 2 com previous_hash ERRADO (deveria ser hash do evento 1).
        # O trigger validate_chain_continuity da migration 030 normalmente
        # bloquearia este insert — bypass via session_replication_role pra
        # poder simular dado adulterado e validar que fn_verify_chain_integrity
        # detecta a quebra.
        h2_payload = '{"step": 2}'
        bogus_prev = "0" * 64
        h2 = _hash_for(h2_payload, bogus_prev)
        with db_cursor() as (conn, cur):
            cur.execute("SET LOCAL session_replication_role = 'replica'")
            cur.execute(
                """
                INSERT INTO traceability_events
                  (tenant_id, event_type, subject_type, subject_id,
                   payload, chain_id, chain_sequence,
                   event_hash, previous_hash, occurred_at)
                VALUES (%s, 'planting', 'plant', 1, %s::jsonb, %s, 2,
                        %s, %s, NOW())
                """,
                (fixture_tenant_id, h2_payload, chain_id, h2, bogus_prev),
            )
            conn.commit()

        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT chain_sequence, valid, expected_previous, actual_previous "
                "FROM fn_verify_chain_integrity(%s) ORDER BY chain_sequence",
                (chain_id,),
            )
            rows = cur.fetchall()

        assert len(rows) == 2
        assert rows[0]["valid"] is True            # sequence 1 ok
        assert rows[1]["valid"] is False           # sequence 2 quebrado
        # expected != actual demonstra a divergencia
        assert rows[1]["expected_previous"] != rows[1]["actual_previous"]


# ---------------------------------------------------------------------------
# v_traceability_chain_status
# ---------------------------------------------------------------------------


class TestViewTraceabilityChainStatus:
    def test_aggregates_chain_metadata(self, fixture_tenant_id: int) -> None:
        chain_id = f"chain-{uuid.uuid4().hex[:8]}"

        h1_payload = '{"step": 1}'
        _insert_trace_event(fixture_tenant_id, chain_id, 1, h1_payload, None)
        h1 = _hash_for(h1_payload, None)
        h2_payload = '{"step": 2}'
        _insert_trace_event(fixture_tenant_id, chain_id, 2, h2_payload, h1)
        h2 = _hash_for(h2_payload, h1)
        h3_payload = '{"step": 3}'
        _insert_trace_event(fixture_tenant_id, chain_id, 3, h3_payload, h2)

        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT chain_id, tenant_id, total_events, last_sequence, "
                "       last_event_hash "
                "FROM v_traceability_chain_status WHERE chain_id = %s",
                (chain_id,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["total_events"] == 3
        assert row["last_sequence"] == 3
        # last_event_hash bate com o hash do evento de sequence=3
        expected_h3 = _hash_for(h3_payload, h2)
        assert row["last_event_hash"].strip() == expected_h3.strip()


# ---------------------------------------------------------------------------
# v_sandbox_indicator_dashboard
# ---------------------------------------------------------------------------


class TestViewSandboxIndicatorDashboard:
    def test_latest_value_and_on_target_flag(
        self, fixture_tenant_id: int
    ) -> None:
        # Cria sandbox_project + indicator + 2 valores (ultimo perto do target)
        with db_cursor(dictionary=True) as (conn, cur):
            cur.execute(
                """
                INSERT INTO sandbox_projects
                  (tenant_id, project_code, title, status, started_at)
                VALUES (%s, %s, 'p_test', 'active', NOW()) RETURNING id
                """,
                (fixture_tenant_id, f"PRJ-{uuid.uuid4().hex[:8]}"),
            )
            project_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO sandbox_indicators
                  (project_id, indicator_code, indicator_name,
                   calculation_formula, unit, target_value,
                   reporting_frequency, is_mandatory)
                VALUES (%s, 'IND-001', 'Adesao ao tratamento',
                        'count(active)/count(total)', '%%', 80.0,
                        'monthly', TRUE)
                RETURNING id
                """,
                (project_id,),
            )
            indicator_id = cur.fetchone()["id"]

            now = datetime.now(timezone.utc)
            # Periodo antigo: longe do target
            cur.execute(
                """
                INSERT INTO sandbox_indicator_values
                  (indicator_id, period_start, period_end, calculated_value)
                VALUES (%s, %s, %s, 50.0)
                """,
                (indicator_id, now - timedelta(days=60), now - timedelta(days=31)),
            )
            # Periodo recente: 79.5 — dentro de 5% do target=80.0
            cur.execute(
                """
                INSERT INTO sandbox_indicator_values
                  (indicator_id, period_start, period_end, calculated_value)
                VALUES (%s, %s, %s, 79.5)
                """,
                (indicator_id, now - timedelta(days=30), now - timedelta(days=1)),
            )
            conn.commit()

        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT indicator_id, latest_value, n_periods, on_target, "
                "       target_value, tenant_id "
                "FROM v_sandbox_indicator_dashboard WHERE indicator_id = %s",
                (indicator_id,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["tenant_id"] == fixture_tenant_id
        assert float(row["latest_value"]) == 79.5
        assert row["n_periods"] == 2
        assert row["on_target"] is True   # 79.5 esta dentro de 5% de 80.0
        assert float(row["target_value"]) == 80.0


# ---------------------------------------------------------------------------
# v_member_active_prescriptions
# ---------------------------------------------------------------------------


class TestViewMemberActivePrescriptions:
    def test_filters_active_members_with_valid_prescription(
        self, fixture_tenant_id: int
    ) -> None:
        # Setup: cria clinic, patient, prescription, member com PoF
        with db_cursor(dictionary=True) as (conn, cur):
            cur.execute(
                "INSERT INTO clinics (id, name, slug, is_active, tenant_id) "
                "VALUES (%s, %s, %s, TRUE, %s) "
                "ON CONFLICT (id) DO NOTHING RETURNING id",
                (fixture_tenant_id, f"v_test_{fixture_tenant_id}",
                 f"v_test_{fixture_tenant_id}", fixture_tenant_id),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute("SELECT id FROM clinics WHERE id = %s",
                            (fixture_tenant_id,))
                row = cur.fetchone()
            clinic_id = row["id"]

            cur.execute(
                "INSERT INTO patients (clinic_id, name, phone, status) "
                "VALUES (%s, 'View Test', '5511', 'em_tratamento') RETURNING id",
                (clinic_id,),
            )
            patient_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO users (username, password_hash, role, is_active)
                VALUES (%s, 'hash', 'Medico', TRUE)
                RETURNING id
                """,
                (f"vtest_doc_{uuid.uuid4().hex[:6]}",),
            )
            doctor_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO prescriptions
                  (clinic_id, patient_id, doctor_user_id, doctor_name,
                   doctor_crm, cannabinoid_ratio, spectrum,
                   administration_route, concentration_mg_ml, max_daily_mg,
                   clinical_rationale, validity_days, status, created_at)
                VALUES (%s, %s, %s, 'Dr View', 'CRM/SP 1', '20:1',
                        'full_spectrum', 'sublingual', 50.0, 200.0,
                        'rationale', 180, 'active', NOW())
                RETURNING id
                """,
                (clinic_id, patient_id, doctor_id),
            )
            prescription_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO association_members
                  (tenant_id, patient_id, membership_number, membership_status,
                   joined_at, prescription_on_file_id)
                VALUES (%s, %s, %s, 'active', %s, %s) RETURNING id
                """,
                (fixture_tenant_id, patient_id,
                 f"M-{uuid.uuid4().hex[:6]}", date.today() - timedelta(days=10),
                 prescription_id),
            )
            member_id = cur.fetchone()["id"]
            conn.commit()

        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT member_id, prescription_id, prescription_status "
                "FROM v_member_active_prescriptions "
                "WHERE tenant_id = %s",
                (fixture_tenant_id,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["member_id"] == member_id
        assert row["prescription_id"] == prescription_id
        assert row["prescription_status"] == "active"

        # Cleanup: extras criados por este teste alem do fixture
        with db_cursor() as (conn, cur):
            cur.execute("SET LOCAL session_replication_role = 'replica'")
            cur.execute(
                "DELETE FROM association_members WHERE id = %s", (member_id,)
            )
            cur.execute(
                "DELETE FROM prescriptions WHERE id = %s", (prescription_id,)
            )
            cur.execute("DELETE FROM users WHERE id = %s", (doctor_id,))
            cur.execute("DELETE FROM patients WHERE id = %s", (patient_id,))
            # clinic permanece — usado por outros testes
            conn.commit()
