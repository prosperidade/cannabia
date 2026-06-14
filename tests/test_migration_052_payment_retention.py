"""
Validacao estatica da migration 050 (FIN-2 — retencao do trilho de pagamento).

Garante por inspecao do SQL que a migration:
1. Cria payment_data_purge_events (tracking, espelha 044).
2. Cria o indice de received_at em payment_transactions (filtro do expurgo).
3. Nao escreve em schema_migrations manualmente.
4. Tem down que dropa exatamente a tabela e o indice, sem destruir dados.

Validacao comportamental (UP->DOWN->UP contra Postgres real) registrada como
evidencia no PR do Track C.
"""
from __future__ import annotations

from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION = MIGRATIONS_DIR / "052_payment_data_retention.sql"
DOWN = MIGRATIONS_DIR / "down" / "052_payment_data_retention_down.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql() -> str:
    assert MIGRATION.exists(), f"migration ausente: {MIGRATION}"
    content = _read(MIGRATION)
    assert content.strip(), "migration 052 esta vazia"
    return content


@pytest.fixture(scope="module")
def down_sql() -> str:
    assert DOWN.exists(), f"down ausente: {DOWN}"
    return _read(DOWN)


class TestStructure:
    def test_header_references_source(self, sql: str) -> None:
        assert "FIN-2" in sql
        assert "R2" in sql

    def test_creates_tracking_table(self, sql: str) -> None:
        assert "CREATE TABLE IF NOT EXISTS payment_data_purge_events" in sql
        for col in ("cutoff_timestamp", "dry_run", "retention_days",
                    "tx_payloads_redacted", "webhook_logs_redacted",
                    "rows_failed", "executor_host"):
            assert col in sql, f"coluna ausente: {col}"

    def test_creates_received_index(self, sql: str) -> None:
        assert "idx_payment_transactions_received" in sql
        assert "payment_transactions (received_at)" in sql

    def test_no_manual_schema_migrations_write(self, sql: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql
        assert "UPDATE schema_migrations" not in sql

    def test_idempotent_guards(self, sql: str) -> None:
        assert "CREATE TABLE IF NOT EXISTS" in sql
        assert "CREATE INDEX IF NOT EXISTS" in sql

    def test_no_destructive_ddl(self, sql: str) -> None:
        assert "DROP TABLE" not in sql
        assert "DROP COLUMN" not in sql


class TestDownScript:
    def test_down_drops_table_and_index(self, down_sql: str) -> None:
        assert "DROP TABLE IF EXISTS payment_data_purge_events" in down_sql
        assert "DROP INDEX IF EXISTS idx_payment_transactions_received" in down_sql

    def test_down_is_non_destructive_to_payment_data(self, down_sql: str) -> None:
        code = "\n".join(
            line for line in down_sql.splitlines()
            if not line.lstrip().startswith("--")
        )
        # nao toca as tabelas de dados financeiros
        assert "DROP TABLE IF EXISTS payment_transactions" not in code
        assert "DROP TABLE IF EXISTS payment_requests" not in code
        assert "DELETE FROM payment" not in code
