"""
Validacao estatica da migration 053 (OBS-1 — heartbeat de verificacao de backup).

Garante por inspecao do SQL que a migration:
1. Cria backup_verification_events com os campos de heartbeat.
2. Cria indices de started_at e (success, started_at) para o monitor.
3. Nao escreve em schema_migrations manualmente.
4. Down dropa tabela + indices sem destruir dados de producao.

Validacao comportamental (UP->DOWN->UP contra Postgres real) registrada como
evidencia no PR do Track C.
"""
from __future__ import annotations

from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION = MIGRATIONS_DIR / "053_backup_verification_events.sql"
DOWN = MIGRATIONS_DIR / "down" / "053_backup_verification_events_down.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql() -> str:
    assert MIGRATION.exists(), f"migration ausente: {MIGRATION}"
    content = _read(MIGRATION)
    assert content.strip(), "migration 053 esta vazia"
    return content


@pytest.fixture(scope="module")
def down_sql() -> str:
    assert DOWN.exists(), f"down ausente: {DOWN}"
    return _read(DOWN)


class TestStructure:
    def test_header_references_source(self, sql: str) -> None:
        assert "OBS-1" in sql
        assert "BUG-001" in sql

    def test_creates_table_with_heartbeat_columns(self, sql: str) -> None:
        assert "CREATE TABLE IF NOT EXISTS backup_verification_events" in sql
        for col in ("started_at", "finished_at", "dump_bytes", "restore_list_lines",
                    "sample_restore_ddl_lines", "sha256", "success",
                    "executor_host", "error_message"):
            assert col in sql, f"coluna ausente: {col}"

    def test_creates_monitor_indexes(self, sql: str) -> None:
        assert "idx_backup_verification_started" in sql
        assert "idx_backup_verification_success" in sql

    def test_no_manual_schema_migrations_write(self, sql: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql
        assert "UPDATE schema_migrations" not in sql

    def test_idempotent_guards(self, sql: str) -> None:
        assert "CREATE TABLE IF NOT EXISTS" in sql
        assert sql.count("CREATE INDEX IF NOT EXISTS") >= 2

    def test_no_destructive_ddl(self, sql: str) -> None:
        assert "DROP TABLE" not in sql
        assert "DROP COLUMN" not in sql


class TestDownScript:
    def test_down_drops_table_and_indexes(self, down_sql: str) -> None:
        assert "DROP TABLE IF EXISTS backup_verification_events" in down_sql
        assert "DROP INDEX IF EXISTS idx_backup_verification_started" in down_sql
        assert "DROP INDEX IF EXISTS idx_backup_verification_success" in down_sql

    def test_down_is_non_destructive_to_other_data(self, down_sql: str) -> None:
        code = "\n".join(
            line for line in down_sql.splitlines()
            if not line.lstrip().startswith("--")
        )
        assert "DELETE FROM" not in code
        assert "payment" not in code
