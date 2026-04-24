"""
Tests da migration 037 — Seed data sandbox (F6.3 do docs/BACKLOG_SCC.md).

Cobre:
  1. Static analysis: funcoes declaradas, conteudo do catalogo presente.
  2. Integration: seed_sandbox_defaults popula um tenant; idempotencia
     via re-execucao; helper seed_sandbox_defaults_all_associations
     popula apenas tenants do tipo 'association' que ainda nao tem
     sanitary_risks; tenant inexistente levanta excecao.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from src.infra.database import db_cursor


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION_037 = MIGRATIONS_DIR / "037_seed_data_sandbox.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql_037() -> str:
    assert MIGRATION_037.exists(), f"migration ausente: {MIGRATION_037}"
    content = _read(MIGRATION_037)
    assert content.strip(), "migration 037 esta vazia"
    return content


# ===========================================================================
# Static analysis
# ===========================================================================


class TestStructure:
    def test_has_header(self, sql_037: str) -> None:
        assert "Migration 037" in sql_037
        assert "F6.3" in sql_037 or "BACKLOG_SCC" in sql_037

    def test_no_manual_schema_migrations_insert(self, sql_037: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql_037
        assert "UPDATE schema_migrations" not in sql_037


class TestExpectedFunctions:
    @pytest.mark.parametrize(
        "fn_name",
        ["seed_sandbox_defaults", "seed_sandbox_defaults_all_associations"],
    )
    def test_function_declared(self, sql_037: str, fn_name: str) -> None:
        assert f"CREATE OR REPLACE FUNCTION {fn_name}" in sql_037


class TestCatalogContent:
    def test_has_10_sanitary_risks(self, sql_037: str) -> None:
        # Conta as 10 risk_code esperados
        for code in [
            "RISK-CONT-001", "RISK-CONT-002", "RISK-DOSE-001", "RISK-DOSE-002",
            "RISK-INTER-001", "RISK-PV-001", "RISK-TRACE-001",
            "RISK-DATA-001", "RISK-SUPPL-001", "RISK-LEGAL-001",
        ]:
            assert code in sql_037, f"risk_code {code} ausente no catalogo"

    def test_has_10_sops(self, sql_037: str) -> None:
        for code in [
            "SOP-CULT-001", "SOP-CULT-002", "SOP-EXT-001",
            "SOP-QC-001", "SOP-QC-002", "SOP-DISP-001",
            "SOP-PV-001", "SOP-PV-002", "SOP-GOV-001", "SOP-GOV-002",
        ]:
            assert code in sql_037, f"SOP code {code} ausente no catalogo"

    def test_idempotent_inserts(self, sql_037: str) -> None:
        # Os dois INSERTs precisam ter ON CONFLICT DO NOTHING
        assert sql_037.count("ON CONFLICT (tenant_id, risk_code) DO NOTHING") == 1
        assert sql_037.count("ON CONFLICT (tenant_id, code) DO NOTHING") == 1


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


@pytest.fixture
def fixture_tenant_id() -> int:
    suffix = uuid.uuid4().hex[:8]
    name = f"seed_test_{suffix}"
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
            "DELETE FROM sanitary_risks WHERE tenant_id = %s", (tenant_id,)
        )
        cur.execute("DELETE FROM sops WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
        conn.commit()


class TestSeedSandboxDefaults:
    def test_inserts_10_risks_and_10_sops(self, fixture_tenant_id: int) -> None:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT object_type, inserted "
                "FROM seed_sandbox_defaults(%s) ORDER BY object_type",
                (fixture_tenant_id,),
            )
            rows = cur.fetchall()

        result = {r["object_type"]: r["inserted"] for r in rows}
        assert result["sanitary_risks"] == 10
        assert result["sops"] == 10

    def test_seeded_data_is_present(self, fixture_tenant_id: int) -> None:
        with db_cursor(dictionary=True) as (conn, cur):
            cur.execute(
                "SELECT * FROM seed_sandbox_defaults(%s)", (fixture_tenant_id,)
            )
            cur.fetchall()
            conn.commit()

            cur.execute(
                "SELECT COUNT(*) AS n FROM sanitary_risks WHERE tenant_id = %s",
                (fixture_tenant_id,),
            )
            assert cur.fetchone()["n"] == 10

            cur.execute(
                "SELECT COUNT(*) AS n FROM sops WHERE tenant_id = %s",
                (fixture_tenant_id,),
            )
            assert cur.fetchone()["n"] == 10

    def test_idempotent_second_call_inserts_zero(
        self, fixture_tenant_id: int
    ) -> None:
        with db_cursor(dictionary=True) as (conn, cur):
            cur.execute(
                "SELECT * FROM seed_sandbox_defaults(%s)", (fixture_tenant_id,)
            )
            cur.fetchall()
            conn.commit()
            # Segunda chamada — todos ON CONFLICT, 0 inseridos
            cur.execute(
                "SELECT object_type, inserted "
                "FROM seed_sandbox_defaults(%s) ORDER BY object_type",
                (fixture_tenant_id,),
            )
            rows = cur.fetchall()

        result = {r["object_type"]: r["inserted"] for r in rows}
        assert result["sanitary_risks"] == 0
        assert result["sops"] == 0

    def test_critical_risks_are_present(self, fixture_tenant_id: int) -> None:
        # Os 2 riscos critical (TRACE e DATA) refletem os invariantes
        # do Art. 17 — devem estar presentes para que o catalogo seja util.
        with db_cursor(dictionary=True) as (conn, cur):
            cur.execute("SELECT * FROM seed_sandbox_defaults(%s)",
                        (fixture_tenant_id,))
            cur.fetchall()
            conn.commit()
            cur.execute(
                "SELECT risk_code, risk_level FROM sanitary_risks "
                "WHERE tenant_id = %s AND risk_level = 'critical' "
                "ORDER BY risk_code",
                (fixture_tenant_id,),
            )
            rows = cur.fetchall()

        codes = {r["risk_code"] for r in rows}
        assert "RISK-TRACE-001" in codes
        assert "RISK-DATA-001" in codes

    def test_raises_on_missing_tenant(self) -> None:
        # tenant_id=999999999 nao existe
        with db_cursor() as (_, cur):
            with pytest.raises(Exception) as exc_info:
                cur.execute(
                    "SELECT * FROM seed_sandbox_defaults(%s)", (999_999_999,)
                )
                cur.fetchall()
        # Mensagem deve mencionar o tenant inexistente
        assert "999999999" in str(exc_info.value) or "nao existe" in str(exc_info.value)


class TestSeedAllAssociations:
    def test_skips_tenants_with_existing_data(
        self, fixture_tenant_id: int
    ) -> None:
        # Pre-popula o tenant — helper deve pular
        with db_cursor() as (conn, cur):
            cur.execute(
                "SELECT * FROM seed_sandbox_defaults(%s)", (fixture_tenant_id,)
            )
            cur.fetchall()
            conn.commit()

        with db_cursor(dictionary=True) as (_, cur):
            cur.execute("SELECT * FROM seed_sandbox_defaults_all_associations()")
            rows = cur.fetchall()

        # O fixture_tenant_id NAO pode estar nas linhas retornadas
        # (porque ja tem sanitary_risks)
        ids = [r["tenant_id"] for r in rows]
        assert fixture_tenant_id not in ids

    def test_includes_empty_associations(self, fixture_tenant_id: int) -> None:
        # fixture_tenant_id e association sem sanitary_risks ainda
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute("SELECT * FROM seed_sandbox_defaults_all_associations()")
            rows = cur.fetchall()

        ids = {r["tenant_id"] for r in rows}
        assert fixture_tenant_id in ids
        # E o seed reportou contagens corretas
        for r in rows:
            if r["tenant_id"] == fixture_tenant_id:
                assert r["sanitary_risks"] == 10
                assert r["sops"] == 10
                break
