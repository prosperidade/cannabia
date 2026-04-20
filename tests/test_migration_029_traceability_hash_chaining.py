"""
Static validation of migration 029 (Traceability Events — hash chaining).

Valida por inspecao estatica do SQL que a migration:

1. Cria a tabela traceability_events prevista no doc 25 §7.6.
2. Respeita a estrutura de hash chaining (chain_id, chain_sequence,
   event_hash, previous_hash).
3. Usa BIGSERIAL + BIGINT em colunas de alta escala.
4. Tem UNIQUE em (chain_id, chain_sequence) e em event_hash.
5. Cria os 5 indexes previstos no doc 25.
6. NAO cria triggers (esses ficam em 030).
7. E idempotente (IF NOT EXISTS em CREATE TABLE e CREATE INDEX).
8. Tem down-script simples (apenas drop da tabela).
"""

from __future__ import annotations

from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION_029 = MIGRATIONS_DIR / "029_traceability_hash_chaining.sql"
MIGRATION_029_DOWN = MIGRATIONS_DIR / "down" / "029_traceability_hash_chaining_down.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql_029() -> str:
    assert MIGRATION_029.exists(), f"migration ausente: {MIGRATION_029}"
    content = _read(MIGRATION_029)
    assert content.strip(), "migration 029 esta vazia"
    return content


@pytest.fixture(scope="module")
def sql_029_down() -> str:
    assert MIGRATION_029_DOWN.exists(), f"down ausente: {MIGRATION_029_DOWN}"
    return _read(MIGRATION_029_DOWN)


@pytest.fixture(scope="module")
def sql_029_code(sql_029: str) -> str:
    return "\n".join(
        line for line in sql_029.splitlines()
        if not line.lstrip().startswith("--")
    )


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

class TestMigration029Structure:
    def test_has_header(self, sql_029: str) -> None:
        assert "Migration 029" in sql_029
        assert "Traceability Events" in sql_029
        assert "Hash Chaining" in sql_029

    def test_references_doc25(self, sql_029: str) -> None:
        assert "§7.6" in sql_029
        assert "doc 25" in sql_029 or "25_SCC_DATA_MODEL" in sql_029

    def test_mentions_deferred_triggers(self, sql_029: str) -> None:
        # Rastreabilidade: comenta que triggers ficam em 030.
        assert "030" in sql_029
        assert "trigger" in sql_029.lower()

    def test_no_manual_schema_migrations_insert(self, sql_029: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql_029


# ---------------------------------------------------------------------------
# Tabela criada
# ---------------------------------------------------------------------------

class TestTraceabilityEventsTable:
    def test_creates_table(self, sql_029: str) -> None:
        assert "CREATE TABLE IF NOT EXISTS traceability_events" in sql_029

    def test_creates_exactly_one_table(self, sql_029_code: str) -> None:
        assert sql_029_code.count("CREATE TABLE IF NOT EXISTS") == 1
        assert sql_029_code.count("CREATE TABLE ") == 1


class TestTraceabilityEventsColumns:
    def test_bigserial_pk(self, sql_029: str) -> None:
        # BIGSERIAL porque alta escala (tabela acumula indefinidamente).
        assert "id             BIGSERIAL PRIMARY KEY" in sql_029

    @pytest.mark.parametrize(
        "column_decl",
        [
            "tenant_id      INT NOT NULL REFERENCES tenants(id)",
            "event_type     VARCHAR(64) NOT NULL",
            "subject_type   VARCHAR(32) NOT NULL",
            "subject_id     BIGINT NOT NULL",
            "actor_user_id  INT REFERENCES users(id)",
            "actor_role     VARCHAR(64)",
            "geo_reference  GEOGRAPHY(POINT, 4326)",
            "payload        JSONB NOT NULL",
            "chain_id       VARCHAR(128) NOT NULL",
            "chain_sequence BIGINT NOT NULL",
            "event_hash     CHAR(64) NOT NULL",
            "previous_hash  CHAR(64)",
            "occurred_at    TIMESTAMPTZ NOT NULL",
            "created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        ],
    )
    def test_has_column(self, sql_029: str, column_decl: str) -> None:
        assert column_decl in sql_029

    def test_subject_id_is_bigint(self, sql_029: str) -> None:
        # subject_id precisa ser BIGINT (nao INT) porque aponta para PKs de
        # tabelas que podem ter BIGSERIAL (ex.: sop_evidences).
        assert "subject_id     BIGINT NOT NULL" in sql_029


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

class TestTraceabilityEventsConstraints:
    def test_unique_chain_sequence(self, sql_029: str) -> None:
        assert "CONSTRAINT uq_trace_chain UNIQUE (chain_id, chain_sequence)" in sql_029

    def test_unique_event_hash(self, sql_029: str) -> None:
        # Colisao de hash = bug ou ataque; UNIQUE garante deteccao.
        assert "CONSTRAINT uq_trace_event_hash UNIQUE (event_hash)" in sql_029

    def test_chain_sequence_positive_check(self, sql_029: str) -> None:
        # Mesmo pattern de sop_evidences em 027: sequencia comeca em 1.
        assert "CONSTRAINT chk_trace_sequence CHECK (chain_sequence >= 1)" in sql_029


# ---------------------------------------------------------------------------
# Indexes (doc 25 §7.6)
# ---------------------------------------------------------------------------

class TestTraceabilityEventsIndexes:
    @pytest.mark.parametrize(
        "index_decl",
        [
            "CREATE INDEX IF NOT EXISTS idx_trace_tenant ON traceability_events (tenant_id)",
            "CREATE INDEX IF NOT EXISTS idx_trace_chain ON traceability_events (chain_id)",
            "CREATE INDEX IF NOT EXISTS idx_trace_subject",
            "CREATE INDEX IF NOT EXISTS idx_trace_type ON traceability_events (event_type)",
            "CREATE INDEX IF NOT EXISTS idx_trace_occurred",
        ],
    )
    def test_has_index(self, sql_029: str, index_decl: str) -> None:
        assert index_decl in sql_029

    def test_creates_five_indexes(self, sql_029_code: str) -> None:
        assert sql_029_code.count("CREATE INDEX") == 5

    def test_subject_index_is_composite(self, sql_029: str) -> None:
        # idx_trace_subject precisa ser composito (subject_type, subject_id)
        # porque e o padrao natural de query (buscar eventos de uma entidade).
        assert "(subject_type, subject_id)" in sql_029


# ---------------------------------------------------------------------------
# Escopo — triggers ficam em 030
# ---------------------------------------------------------------------------

class TestMigration029Scope:
    def test_does_not_create_triggers(self, sql_029: str) -> None:
        # Triggers ficam em 030 (append-only protection + chain validation).
        assert "CREATE TRIGGER" not in sql_029

    def test_does_not_create_functions(self, sql_029: str) -> None:
        # prevent_update_delete ja foi criada em 027.
        # validate_chain_continuity sera criada em 030.
        assert "CREATE FUNCTION" not in sql_029
        assert "CREATE OR REPLACE FUNCTION" not in sql_029

    def test_does_not_recreate_existing_tables(self, sql_029: str) -> None:
        # Migrations anteriores ja criaram essas tabelas.
        for existing in (
            "tenants", "users", "sop_evidences", "genetic_matrices",
            "cultivation_batches", "harvests", "extractions",
            "preparations", "dispensations",
        ):
            assert f"CREATE TABLE {existing}" not in sql_029
            assert f"CREATE TABLE IF NOT EXISTS {existing}" not in sql_029


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------

class TestMigration029Idempotency:
    def test_create_table_uses_if_not_exists(self, sql_029_code: str) -> None:
        assert sql_029_code.count("CREATE TABLE") == sql_029_code.count(
            "CREATE TABLE IF NOT EXISTS"
        )

    def test_all_indexes_use_if_not_exists(self, sql_029_code: str) -> None:
        assert sql_029_code.count("CREATE INDEX") == sql_029_code.count(
            "CREATE INDEX IF NOT EXISTS"
        )


# ---------------------------------------------------------------------------
# Down script
# ---------------------------------------------------------------------------

class TestMigration029Down:
    def test_has_header(self, sql_029_down: str) -> None:
        assert "Down migration 029" in sql_029_down

    def test_drops_table(self, sql_029_down: str) -> None:
        assert "DROP TABLE IF EXISTS traceability_events" in sql_029_down

    def test_uses_if_exists(self, sql_029_down: str) -> None:
        code = "\n".join(
            line for line in sql_029_down.splitlines()
            if not line.lstrip().startswith("--")
        )
        assert code.count("DROP TABLE") == code.count("DROP TABLE IF EXISTS")

    def test_does_not_drop_postgis_extension(self, sql_029_down: str) -> None:
        # postgis e compartilhada com 028; down de 029 nao toca nela.
        assert "DROP EXTENSION" not in sql_029_down

    def test_does_not_touch_preexisting_tables(self, sql_029_down: str) -> None:
        for preexisting in (
            "tenants", "users", "genetic_matrices", "seed_lots",
            "cultivation_batches", "plants", "harvests", "extractions",
            "preparations", "lab_analyses", "dispensations",
        ):
            assert f"DROP TABLE IF EXISTS {preexisting}" not in sql_029_down
            assert f"DROP TABLE {preexisting}" not in sql_029_down
