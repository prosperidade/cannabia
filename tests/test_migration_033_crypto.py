"""Static validation of migration 033 (Crypto Schema — F5.1 do SCC).

Valida por inspecao estatica do SQL que a migration:

1. Cria as 2 tabelas previstas no doc 25 §§10.1-10.2.
2. blockchain_anchors.id usa BIGSERIAL e tenant_id e NULLABLE.
3. Aplica CHECKs whitelist (anchor_scope, blockchain_network,
   verification_status) + defensivos de ordem temporal e contagem.
4. PK composta em anchor_event_mappings + index reverso por evento.
5. Nao recria tabelas de outras fases.
6. Tem down-script reverso paralelo.
"""

from __future__ import annotations

from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION_033 = MIGRATIONS_DIR / "033_crypto_schema.sql"
MIGRATION_033_DOWN = MIGRATIONS_DIR / "down" / "033_crypto_schema_down.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql_033() -> str:
    assert MIGRATION_033.exists()
    content = _read(MIGRATION_033)
    assert content.strip()
    return content


@pytest.fixture(scope="module")
def sql_033_down() -> str:
    assert MIGRATION_033_DOWN.exists()
    return _read(MIGRATION_033_DOWN)


@pytest.fixture(scope="module")
def sql_033_code(sql_033: str) -> str:
    return "\n".join(
        line for line in sql_033.splitlines()
        if not line.lstrip().startswith("--")
    )


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

class TestMigration033Structure:
    def test_has_header(self, sql_033: str) -> None:
        assert "Migration 033" in sql_033
        assert "Crypto Schema" in sql_033

    def test_references_backlog_and_doc25(self, sql_033: str) -> None:
        assert "F5.1" in sql_033
        assert "BACKLOG_SCC" in sql_033 or "doc 25" in sql_033 or "25_SCC_DATA_MODEL" in sql_033

    def test_references_doc25_sections(self, sql_033: str) -> None:
        for s in ("§10.1", "§10.2"):
            assert s in sql_033, f"falta {s}"

    def test_no_manual_schema_migrations_insert(self, sql_033: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql_033


# ---------------------------------------------------------------------------
# Tabelas criadas
# ---------------------------------------------------------------------------

class TestMigration033Tables:
    @pytest.mark.parametrize(
        "table",
        ["blockchain_anchors", "anchor_event_mappings"],
    )
    def test_creates_table(self, sql_033: str, table: str) -> None:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql_033

    def test_creates_exactly_two_tables(self, sql_033_code: str) -> None:
        assert sql_033_code.count("CREATE TABLE IF NOT EXISTS") == 2
        assert sql_033_code.count("CREATE TABLE ") == sql_033_code.count(
            "CREATE TABLE IF NOT EXISTS"
        )


# ---------------------------------------------------------------------------
# blockchain_anchors (doc 25 §10.1)
# ---------------------------------------------------------------------------

class TestBlockchainAnchors:
    def test_uses_bigserial_id(self, sql_033: str) -> None:
        assert "id                  BIGSERIAL PRIMARY KEY" in sql_033

    def test_tenant_id_is_nullable(self, sql_033: str) -> None:
        # Necessario para anchor_scope='global'.
        assert "tenant_id           INT REFERENCES tenants(id)" in sql_033
        # Sem NOT NULL (a linha nao deve ser "INT NOT NULL REFERENCES").
        assert "tenant_id           INT NOT NULL REFERENCES tenants(id)" not in sql_033

    @pytest.mark.parametrize(
        "column_decl",
        [
            "anchor_scope        VARCHAR(32) NOT NULL",
            "covered_from        TIMESTAMPTZ NOT NULL",
            "covered_until       TIMESTAMPTZ NOT NULL",
            "events_count        BIGINT NOT NULL",
            "merkle_root         CHAR(64) NOT NULL",
            "blockchain_network  VARCHAR(32) NOT NULL",
            "transaction_id      VARCHAR(255) NOT NULL",
            "block_number        BIGINT",
            "block_timestamp     TIMESTAMPTZ",
            "proof_uri           TEXT",
            "proof_hash          CHAR(64)",
            "anchored_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()",
            "verified_at         TIMESTAMPTZ",
            "verification_status VARCHAR(32) NOT NULL DEFAULT 'pending'",
        ],
    )
    def test_has_column(self, sql_033: str, column_decl: str) -> None:
        assert column_decl in sql_033

    def test_anchor_scope_whitelist(self, sql_033: str) -> None:
        assert "CONSTRAINT chk_anchors_scope CHECK" in sql_033
        for scope in ("'global'", "'tenant'", "'project'"):
            assert scope in sql_033

    def test_blockchain_network_whitelist(self, sql_033: str) -> None:
        assert "CONSTRAINT chk_anchors_network CHECK" in sql_033
        for net in ("'bitcoin_ots'", "'polygon'", "'ethereum'"):
            assert net in sql_033

    def test_verification_status_whitelist(self, sql_033: str) -> None:
        assert "CONSTRAINT chk_anchors_verification CHECK" in sql_033
        for st in ("'pending'", "'confirmed'", "'failed'"):
            assert st in sql_033

    def test_coverage_order_check(self, sql_033: str) -> None:
        assert "CONSTRAINT chk_anchors_coverage_order CHECK" in sql_033
        assert "covered_until >= covered_from" in sql_033

    def test_events_count_non_negative(self, sql_033: str) -> None:
        assert "CONSTRAINT chk_anchors_events_count CHECK" in sql_033
        assert "events_count >= 0" in sql_033

    def test_verification_order_check_allows_null(self, sql_033: str) -> None:
        assert "CONSTRAINT chk_anchors_verification_order CHECK" in sql_033
        assert "verified_at IS NULL OR verified_at >= anchored_at" in sql_033

    def test_indexes(self, sql_033: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_anchors_tenant" in sql_033
        assert "CREATE INDEX IF NOT EXISTS idx_anchors_period" in sql_033
        assert "CREATE INDEX IF NOT EXISTS idx_anchors_network" in sql_033

    def test_period_index_is_composite(self, sql_033: str) -> None:
        assert "(covered_from, covered_until)" in sql_033


# ---------------------------------------------------------------------------
# anchor_event_mappings (doc 25 §10.2)
# ---------------------------------------------------------------------------

class TestAnchorEventMappings:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "anchor_id   BIGINT NOT NULL REFERENCES blockchain_anchors(id)",
            "event_table VARCHAR(64) NOT NULL",
            "event_id    BIGINT NOT NULL",
            "event_hash  CHAR(64) NOT NULL",
            "merkle_path JSONB NOT NULL",
        ],
    )
    def test_has_column(self, sql_033: str, column_decl: str) -> None:
        assert column_decl in sql_033

    def test_composite_primary_key(self, sql_033: str) -> None:
        assert (
            "CONSTRAINT pk_anchor_event_mappings PRIMARY KEY (anchor_id, event_table, event_id)"
            in sql_033
        )

    def test_reverse_index_exists(self, sql_033: str) -> None:
        # Index (event_table, event_id) para lookup "este evento esta ancorado?"
        assert "CREATE INDEX IF NOT EXISTS idx_anchor_mappings_event" in sql_033
        assert "(event_table, event_id)" in sql_033


# ---------------------------------------------------------------------------
# Ordem de criacao (FK)
# ---------------------------------------------------------------------------

class TestMigration033CreationOrder:
    def test_anchors_before_mappings(self, sql_033: str) -> None:
        pos_a = sql_033.find("CREATE TABLE IF NOT EXISTS blockchain_anchors")
        pos_m = sql_033.find("CREATE TABLE IF NOT EXISTS anchor_event_mappings")
        assert 0 < pos_a < pos_m


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------

class TestMigration033Idempotency:
    def test_create_table_if_not_exists(self, sql_033_code: str) -> None:
        assert sql_033_code.count("CREATE TABLE") == sql_033_code.count(
            "CREATE TABLE IF NOT EXISTS"
        )

    def test_create_index_if_not_exists(self, sql_033_code: str) -> None:
        assert sql_033_code.count("CREATE INDEX") == sql_033_code.count(
            "CREATE INDEX IF NOT EXISTS"
        )


# ---------------------------------------------------------------------------
# Escopo
# ---------------------------------------------------------------------------

class TestMigration033Scope:
    @pytest.mark.parametrize(
        "out_of_scope_table",
        [
            "tenants", "users", "association_members", "preparations",
            "sops", "traceability_events",
            "adverse_events", "pharmacovigilance_notifications",
            "sanitary_risks", "risk_controls",
            "sandbox_projects", "regulatory_submissions", "regulatory_reports",
        ],
    )
    def test_does_not_recreate_out_of_scope(self, sql_033: str, out_of_scope_table: str) -> None:
        assert f"CREATE TABLE {out_of_scope_table}" not in sql_033
        assert f"CREATE TABLE IF NOT EXISTS {out_of_scope_table}" not in sql_033

    def test_does_not_create_triggers(self, sql_033_code: str) -> None:
        # Ancoras sao mutaveis (pending → confirmed). Append-only nao aqui.
        assert "CREATE TRIGGER" not in sql_033_code


# ---------------------------------------------------------------------------
# Down script
# ---------------------------------------------------------------------------

class TestMigration033Down:
    def test_has_header(self, sql_033_down: str) -> None:
        assert "Down migration 033" in sql_033_down

    @pytest.mark.parametrize(
        "table",
        ["anchor_event_mappings", "blockchain_anchors"],
    )
    def test_drops_every_table(self, sql_033_down: str, table: str) -> None:
        assert f"DROP TABLE IF EXISTS {table}" in sql_033_down

    def test_reverse_order_mappings_before_anchors(self, sql_033_down: str) -> None:
        pos_m = sql_033_down.find("DROP TABLE IF EXISTS anchor_event_mappings")
        pos_a = sql_033_down.find("DROP TABLE IF EXISTS blockchain_anchors")
        assert 0 < pos_m < pos_a

    def test_all_drops_use_if_exists(self, sql_033_down: str) -> None:
        code = "\n".join(
            line for line in sql_033_down.splitlines()
            if not line.lstrip().startswith("--")
        )
        assert code.count("DROP TABLE") == code.count("DROP TABLE IF EXISTS")

    def test_does_not_touch_preexisting(self, sql_033_down: str) -> None:
        for preexisting in (
            "tenants", "users", "traceability_events",
            "adverse_events", "sandbox_projects", "regulatory_reports",
        ):
            assert f"DROP TABLE IF EXISTS {preexisting}" not in sql_033_down
            assert f"DROP TABLE {preexisting}" not in sql_033_down
