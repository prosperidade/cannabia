"""
Static validation of migration 030 (Traceability Triggers — doc 25 §§7.7-7.8).

Valida por inspecao estatica do SQL que a migration:

1. Cria o trigger traceability_events_immutable (append-only, reusa
   prevent_update_delete de 027).
2. Cria a funcao validate_chain_continuity.
3. Cria o trigger traceability_events_chain_check (BEFORE INSERT).
4. NAO cria/recreia a funcao prevent_update_delete (ja existe em 027).
5. E idempotente (DO $$ + pg_trigger guard, CREATE OR REPLACE FUNCTION).
6. Tem down-script que dropa triggers + funcao especifica mas preserva
   prevent_update_delete (ainda em uso por sop_evidences).
"""

from __future__ import annotations

from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION_030 = MIGRATIONS_DIR / "030_traceability_triggers.sql"
MIGRATION_030_DOWN = MIGRATIONS_DIR / "down" / "030_traceability_triggers_down.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql_030() -> str:
    assert MIGRATION_030.exists(), f"migration ausente: {MIGRATION_030}"
    content = _read(MIGRATION_030)
    assert content.strip(), "migration 030 esta vazia"
    return content


@pytest.fixture(scope="module")
def sql_030_down() -> str:
    assert MIGRATION_030_DOWN.exists(), f"down ausente: {MIGRATION_030_DOWN}"
    return _read(MIGRATION_030_DOWN)


@pytest.fixture(scope="module")
def sql_030_code(sql_030: str) -> str:
    return "\n".join(
        line for line in sql_030.splitlines()
        if not line.lstrip().startswith("--")
    )


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

class TestMigration030Structure:
    def test_has_header(self, sql_030: str) -> None:
        assert "Migration 030" in sql_030
        assert "Traceability Triggers" in sql_030

    def test_references_doc25_sections(self, sql_030: str) -> None:
        for section in ("§7.7", "§7.8"):
            assert section in sql_030, f"falta referencia a {section}"

    def test_no_manual_schema_migrations_insert(self, sql_030: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql_030


# ---------------------------------------------------------------------------
# Trigger append-only (reusa prevent_update_delete)
# ---------------------------------------------------------------------------

class TestAppendOnlyTrigger:
    def test_creates_immutable_trigger(self, sql_030: str) -> None:
        assert "CREATE TRIGGER traceability_events_immutable" in sql_030
        assert "BEFORE UPDATE OR DELETE ON traceability_events" in sql_030
        assert "EXECUTE FUNCTION prevent_update_delete()" in sql_030

    def test_trigger_guarded_by_pg_trigger(self, sql_030: str) -> None:
        assert "WHERE tgname = 'traceability_events_immutable'" in sql_030

    def test_does_not_recreate_prevent_update_delete(self, sql_030: str) -> None:
        # Essa funcao ja existe desde 027; nao deve ser recriada aqui.
        assert "CREATE OR REPLACE FUNCTION prevent_update_delete" not in sql_030
        assert "CREATE FUNCTION prevent_update_delete" not in sql_030


# ---------------------------------------------------------------------------
# validate_chain_continuity
# ---------------------------------------------------------------------------

class TestValidateChainContinuity:
    def test_creates_function(self, sql_030: str) -> None:
        assert "CREATE OR REPLACE FUNCTION validate_chain_continuity()" in sql_030
        assert "RETURNS TRIGGER" in sql_030
        assert "LANGUAGE plpgsql" in sql_030

    def test_function_looks_up_previous_event(self, sql_030: str) -> None:
        # Funcao precisa buscar o evento anterior (chain_sequence - 1).
        assert "FROM traceability_events" in sql_030
        assert "chain_id = NEW.chain_id" in sql_030
        assert "chain_sequence = NEW.chain_sequence - 1" in sql_030

    def test_function_checks_sequence_greater_than_one(self, sql_030: str) -> None:
        # Primeiro evento da cadeia (seq=1) nao valida — doc 25 §7.8.
        assert "NEW.chain_sequence > 1" in sql_030

    def test_function_uses_is_distinct_from(self, sql_030: str) -> None:
        # IS DISTINCT FROM lida corretamente com NULL (ao contrario de =).
        assert "IS DISTINCT FROM expected_previous" in sql_030

    def test_function_raises_on_mismatch(self, sql_030: str) -> None:
        assert "RAISE EXCEPTION" in sql_030
        assert "Chain continuity violation" in sql_030


# ---------------------------------------------------------------------------
# Trigger chain_check
# ---------------------------------------------------------------------------

class TestChainCheckTrigger:
    def test_creates_chain_check_trigger(self, sql_030: str) -> None:
        assert "CREATE TRIGGER traceability_events_chain_check" in sql_030
        assert "BEFORE INSERT ON traceability_events" in sql_030
        assert "EXECUTE FUNCTION validate_chain_continuity()" in sql_030

    def test_trigger_guarded_by_pg_trigger(self, sql_030: str) -> None:
        assert "WHERE tgname = 'traceability_events_chain_check'" in sql_030


# ---------------------------------------------------------------------------
# Ordem: funcao antes do trigger que a usa
# ---------------------------------------------------------------------------

class TestMigration030Order:
    def test_function_defined_before_chain_check_trigger(self, sql_030: str) -> None:
        pos_fn = sql_030.find("CREATE OR REPLACE FUNCTION validate_chain_continuity")
        pos_trig = sql_030.find("CREATE TRIGGER traceability_events_chain_check")
        assert 0 < pos_fn < pos_trig, (
            "validate_chain_continuity precisa ser definida ANTES do trigger que a usa"
        )


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------

class TestMigration030Idempotency:
    def test_function_uses_or_replace(self, sql_030: str) -> None:
        assert "CREATE OR REPLACE FUNCTION validate_chain_continuity" in sql_030

    def test_triggers_guarded_by_pg_trigger(self, sql_030_code: str) -> None:
        # Ambos triggers em DO $$ com pg_trigger guard.
        assert sql_030_code.count("FROM pg_trigger") >= 2
        assert sql_030_code.count("CREATE TRIGGER") >= 2


# ---------------------------------------------------------------------------
# Escopo
# ---------------------------------------------------------------------------

class TestMigration030Scope:
    def test_does_not_create_tables(self, sql_030_code: str) -> None:
        # 030 e so triggers e funcao — nenhuma DDL de tabela.
        assert "CREATE TABLE" not in sql_030_code

    def test_does_not_create_indexes(self, sql_030_code: str) -> None:
        assert "CREATE INDEX" not in sql_030_code

    def test_does_not_alter_traceability_events(self, sql_030: str) -> None:
        # Nao evolui schema da tabela aqui.
        assert "ALTER TABLE traceability_events" not in sql_030


# ---------------------------------------------------------------------------
# Down script
# ---------------------------------------------------------------------------

class TestMigration030Down:
    def test_has_header(self, sql_030_down: str) -> None:
        assert "Down migration 030" in sql_030_down

    def test_drops_both_triggers(self, sql_030_down: str) -> None:
        assert (
            "DROP TRIGGER IF EXISTS traceability_events_chain_check ON traceability_events"
            in sql_030_down
        )
        assert (
            "DROP TRIGGER IF EXISTS traceability_events_immutable ON traceability_events"
            in sql_030_down
        )

    def test_drops_validate_function(self, sql_030_down: str) -> None:
        assert "DROP FUNCTION IF EXISTS validate_chain_continuity()" in sql_030_down

    def test_preserves_prevent_update_delete(self, sql_030_down: str) -> None:
        # prevent_update_delete ainda e usada por sop_evidences (027).
        # Nao pode ser dropada aqui.
        assert "DROP FUNCTION IF EXISTS prevent_update_delete" not in sql_030_down
        assert "DROP FUNCTION prevent_update_delete" not in sql_030_down

    def test_does_not_drop_traceability_events_table(self, sql_030_down: str) -> None:
        # Schema da tabela pertence a 029; este down so remove os triggers/funcao.
        assert "DROP TABLE" not in sql_030_down

    def test_all_drops_use_if_exists(self, sql_030_down: str) -> None:
        code = "\n".join(
            line for line in sql_030_down.splitlines()
            if not line.lstrip().startswith("--")
        )
        assert code.count("DROP TRIGGER") == code.count("DROP TRIGGER IF EXISTS")
        assert code.count("DROP FUNCTION") == code.count("DROP FUNCTION IF EXISTS")
