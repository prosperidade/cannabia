"""
Static validation of migration 028 (Traceability Schema Base — F2.3 do SCC).

Valida por inspecao estatica do SQL que a migration:

1. Habilita a extensao postgis (requerida por cultivation_batches.geo_reference).
2. Cria as 9 tabelas previstas no doc 25 §§7.1-7.5.
3. Respeita ordem de criacao coerente com as FKs internas
   (genetic_matrices → seed_lots → cultivation_batches → plants/harvests →
   extractions → preparations → dispensations).
4. NAO cria traceability_events (esse fica em 029).
5. NAO cria o trigger append-only (esse fica em 030).
6. Respeita FKs externas para tenants(id), users(id), prescriptions(id),
   association_members(id) e sop_versions(id).
7. Tem down-script paralelo com ordem reversa de DROP.
"""

from __future__ import annotations

from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION_028 = MIGRATIONS_DIR / "028_traceability_schema_base.sql"
MIGRATION_028_DOWN = MIGRATIONS_DIR / "down" / "028_traceability_schema_base_down.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql_028() -> str:
    assert MIGRATION_028.exists(), f"migration ausente: {MIGRATION_028}"
    content = _read(MIGRATION_028)
    assert content.strip(), "migration 028 esta vazia"
    return content


@pytest.fixture(scope="module")
def sql_028_down() -> str:
    assert MIGRATION_028_DOWN.exists(), f"down script ausente: {MIGRATION_028_DOWN}"
    content = _read(MIGRATION_028_DOWN)
    assert content.strip(), "down 028 esta vazio"
    return content


@pytest.fixture(scope="module")
def sql_028_code(sql_028: str) -> str:
    return "\n".join(
        line for line in sql_028.splitlines()
        if not line.lstrip().startswith("--")
    )


# ---------------------------------------------------------------------------
# Structure & rastreabilidade
# ---------------------------------------------------------------------------

class TestMigration028Structure:
    def test_has_header(self, sql_028: str) -> None:
        assert "Migration 028" in sql_028
        assert "Traceability Schema Base" in sql_028

    def test_references_backlog_and_doc25(self, sql_028: str) -> None:
        assert "F2.3" in sql_028
        assert "BACKLOG_SCC" in sql_028 or "doc 25" in sql_028 or "25_SCC_DATA_MODEL" in sql_028

    def test_references_doc25_sections(self, sql_028: str) -> None:
        for section in ("§7.1", "§7.2", "§7.3", "§7.4", "§7.5"):
            assert section in sql_028, f"falta referencia a {section}"

    def test_no_manual_schema_migrations_insert(self, sql_028: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql_028
        assert "UPDATE schema_migrations" not in sql_028


# ---------------------------------------------------------------------------
# PostGIS extension
# ---------------------------------------------------------------------------

class TestPostGISExtension:
    def test_creates_extension(self, sql_028: str) -> None:
        # Idempotente: IF NOT EXISTS permite re-execucao em ambientes com postgis ja instalado.
        assert "CREATE EXTENSION IF NOT EXISTS postgis" in sql_028

    def test_extension_created_before_geography_columns(self, sql_028_code: str) -> None:
        # Usa sql_028_code (sem comentarios) para nao confundir mencoes em prosa
        # no cabecalho com a declaracao SQL efetiva.
        pos_ext = sql_028_code.find("CREATE EXTENSION IF NOT EXISTS postgis")
        pos_geo = sql_028_code.find("GEOGRAPHY(POINT, 4326)")
        assert 0 < pos_ext < pos_geo, (
            "CREATE EXTENSION precisa vir ANTES de qualquer coluna GEOGRAPHY"
        )


# ---------------------------------------------------------------------------
# Tabelas criadas
# ---------------------------------------------------------------------------

class TestMigration028Tables:
    @pytest.mark.parametrize(
        "table",
        [
            "genetic_matrices",
            "seed_lots",
            "cultivation_batches",
            "plants",
            "harvests",
            "extractions",
            "preparations",
            "lab_analyses",
            "dispensations",
        ],
    )
    def test_creates_table(self, sql_028: str, table: str) -> None:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql_028

    def test_creates_exactly_nine_tables(self, sql_028_code: str) -> None:
        assert sql_028_code.count("CREATE TABLE IF NOT EXISTS") == 9
        assert sql_028_code.count("CREATE TABLE ") == sql_028_code.count(
            "CREATE TABLE IF NOT EXISTS"
        )


# ---------------------------------------------------------------------------
# genetic_matrices (doc 25 §7.1)
# ---------------------------------------------------------------------------

class TestGeneticMatrices:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "id               SERIAL PRIMARY KEY",
            "tenant_id        INT NOT NULL REFERENCES tenants(id)",
            "matrix_code      VARCHAR(64) NOT NULL",
            "strain_name      VARCHAR(128)",
            "origin           TEXT",
            "declared_profile JSONB",
            "qr_code          VARCHAR(128) UNIQUE",
            "nft_reference    VARCHAR(255)",
        ],
    )
    def test_has_column(self, sql_028: str, column_decl: str) -> None:
        assert column_decl in sql_028

    def test_unique_tenant_code(self, sql_028: str) -> None:
        assert (
            "CONSTRAINT uq_matrices_tenant_code UNIQUE (tenant_id, matrix_code)"
            in sql_028
        )


# ---------------------------------------------------------------------------
# seed_lots (doc 25 §7.1)
# ---------------------------------------------------------------------------

class TestSeedLots:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "tenant_id   INT NOT NULL REFERENCES tenants(id)",
            "matrix_id   INT REFERENCES genetic_matrices(id)",
            "lot_code    VARCHAR(64) NOT NULL",
            "quantity    INT NOT NULL",
            "received_at DATE NOT NULL",
            "supplier    VARCHAR(255)",
            "qr_code     VARCHAR(128) UNIQUE",
        ],
    )
    def test_has_column(self, sql_028: str, column_decl: str) -> None:
        assert column_decl in sql_028

    def test_quantity_non_negative_check(self, sql_028: str) -> None:
        assert "CONSTRAINT chk_seed_lots_quantity CHECK (quantity >= 0)" in sql_028

    def test_unique_tenant_code(self, sql_028: str) -> None:
        assert (
            "CONSTRAINT uq_seed_lots_tenant_code UNIQUE (tenant_id, lot_code)"
            in sql_028
        )


# ---------------------------------------------------------------------------
# cultivation_batches (doc 25 §7.2) — GEOGRAPHY
# ---------------------------------------------------------------------------

class TestCultivationBatches:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "tenant_id            INT NOT NULL REFERENCES tenants(id)",
            "batch_code           VARCHAR(64) NOT NULL",
            "source_seed_lot_id   INT REFERENCES seed_lots(id)",
            "source_matrix_id     INT REFERENCES genetic_matrices(id)",
            "started_at           DATE NOT NULL",
            "ended_at             DATE",
            "location_description TEXT",
            "geo_reference        GEOGRAPHY(POINT, 4326)",
            "qr_code              VARCHAR(128) UNIQUE",
        ],
    )
    def test_has_column(self, sql_028: str, column_decl: str) -> None:
        assert column_decl in sql_028

    def test_period_check(self, sql_028: str) -> None:
        # Defensivo: ended_at >= started_at.
        assert "CONSTRAINT chk_batches_period CHECK" in sql_028
        assert "ended_at IS NULL OR ended_at >= started_at" in sql_028


# ---------------------------------------------------------------------------
# plants (doc 25 §7.2)
# ---------------------------------------------------------------------------

class TestPlants:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "tenant_id      INT NOT NULL REFERENCES tenants(id)",
            "batch_id       INT NOT NULL REFERENCES cultivation_batches(id)",
            "plant_code     VARCHAR(64) NOT NULL",
            "planted_at     DATE NOT NULL",
            "removed_at     DATE",
            "removal_reason VARCHAR(64)",
        ],
    )
    def test_has_column(self, sql_028: str, column_decl: str) -> None:
        assert column_decl in sql_028

    def test_lifecycle_check(self, sql_028: str) -> None:
        assert "CONSTRAINT chk_plants_lifecycle CHECK" in sql_028
        assert "removed_at IS NULL OR removed_at >= planted_at" in sql_028


# ---------------------------------------------------------------------------
# harvests (doc 25 §7.3)
# ---------------------------------------------------------------------------

class TestHarvests:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "tenant_id      INT NOT NULL REFERENCES tenants(id)",
            "batch_id       INT NOT NULL REFERENCES cultivation_batches(id)",
            "harvest_code   VARCHAR(64) NOT NULL",
            "harvested_at   DATE NOT NULL",
            "plant_ids      INT[] NOT NULL",
            "gross_weight_g NUMERIC(12,3)",
            "net_weight_g   NUMERIC(12,3)",
        ],
    )
    def test_has_column(self, sql_028: str, column_decl: str) -> None:
        assert column_decl in sql_028

    def test_weight_checks(self, sql_028: str) -> None:
        # Defensivos: pesos nao-negativos + liquido <= bruto.
        assert "CONSTRAINT chk_harvests_weights CHECK" in sql_028
        assert "gross_weight_g IS NULL OR gross_weight_g >= 0" in sql_028
        assert "net_weight_g IS NULL OR net_weight_g >= 0" in sql_028
        assert "net_weight_g <= gross_weight_g" in sql_028


# ---------------------------------------------------------------------------
# extractions (doc 25 §7.3)
# ---------------------------------------------------------------------------

class TestExtractions:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "harvest_id         INT NOT NULL REFERENCES harvests(id)",
            "extraction_code    VARCHAR(64) NOT NULL",
            "executed_at        TIMESTAMPTZ NOT NULL",
            "process_parameters JSONB NOT NULL",
            "sop_version_id     INT REFERENCES sop_versions(id)",
            "responsible_id     INT REFERENCES users(id)",
            "output_weight_g    NUMERIC(12,3)",
        ],
    )
    def test_has_column(self, sql_028: str, column_decl: str) -> None:
        assert column_decl in sql_028

    def test_output_weight_check(self, sql_028: str) -> None:
        assert "CONSTRAINT chk_extractions_output CHECK" in sql_028
        assert "output_weight_g IS NULL OR output_weight_g >= 0" in sql_028


# ---------------------------------------------------------------------------
# preparations (doc 25 §7.3)
# ---------------------------------------------------------------------------

class TestPreparations:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "extraction_id         INT NOT NULL REFERENCES extractions(id)",
            "preparation_code      VARCHAR(64) NOT NULL",
            "preparation_type      VARCHAR(64) NOT NULL",
            "produced_at           TIMESTAMPTZ NOT NULL",
            "units_produced        INT NOT NULL",
            "unit_size_ml          NUMERIC(10,3)",
            "sop_version_id        INT REFERENCES sop_versions(id)",
            "warning_label_applied BOOLEAN NOT NULL DEFAULT FALSE",
        ],
    )
    def test_has_column(self, sql_028: str, column_decl: str) -> None:
        assert column_decl in sql_028

    def test_units_positive_check(self, sql_028: str) -> None:
        assert "CONSTRAINT chk_preparations_units CHECK (units_produced > 0)" in sql_028

    def test_unit_size_positive_check(self, sql_028: str) -> None:
        assert "CONSTRAINT chk_preparations_size CHECK" in sql_028
        assert "unit_size_ml IS NULL OR unit_size_ml > 0" in sql_028


# ---------------------------------------------------------------------------
# lab_analyses (doc 25 §7.4)
# ---------------------------------------------------------------------------

class TestLabAnalyses:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "subject_type        VARCHAR(32) NOT NULL",
            "subject_id          INT NOT NULL",
            "lab_name            VARCHAR(255) NOT NULL",
            "report_number       VARCHAR(128) NOT NULL",
            "analysis_date       DATE NOT NULL",
            "cannabinoid_profile JSONB NOT NULL",
            "thc_percent         NUMERIC(6,3)",
            "cbd_percent         NUMERIC(6,3)",
            "conformity_status   VARCHAR(32) NOT NULL",
            "report_uri          TEXT",
            "report_hash         CHAR(64)",
        ],
    )
    def test_has_column(self, sql_028: str, column_decl: str) -> None:
        assert column_decl in sql_028

    def test_subject_type_whitelist(self, sql_028: str) -> None:
        assert "CONSTRAINT chk_lab_subject_type CHECK" in sql_028
        for st in ("'harvest'", "'extraction'", "'preparation'"):
            assert st in sql_028, f"falta subject_type: {st}"

    def test_conformity_whitelist(self, sql_028: str) -> None:
        assert "CONSTRAINT chk_lab_conformity CHECK" in sql_028
        for st in ("'conforming'", "'non_conforming'", "'pending'"):
            assert st in sql_028, f"falta conformity: {st}"

    def test_thc_cbd_range_checks(self, sql_028: str) -> None:
        # Percentuais precisam estar em [0, 100].
        assert "CONSTRAINT chk_lab_thc_range CHECK" in sql_028
        assert "CONSTRAINT chk_lab_cbd_range CHECK" in sql_028
        assert "thc_percent >= 0 AND thc_percent <= 100" in sql_028
        assert "cbd_percent >= 0 AND cbd_percent <= 100" in sql_028

    def test_indexes(self, sql_028: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_lab_tenant" in sql_028
        assert "CREATE INDEX IF NOT EXISTS idx_lab_subject" in sql_028


# ---------------------------------------------------------------------------
# dispensations (doc 25 §7.5)
# ---------------------------------------------------------------------------

class TestDispensations:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "preparation_id       INT NOT NULL REFERENCES preparations(id)",
            "member_id            INT NOT NULL REFERENCES association_members(id)",
            "prescription_id      INT NOT NULL REFERENCES prescriptions(id)",
            "units_dispensed      INT NOT NULL",
            "dispensed_at         TIMESTAMPTZ NOT NULL",
            "dispensed_by         INT REFERENCES users(id)",
            "warning_acknowledged BOOLEAN NOT NULL DEFAULT FALSE",
        ],
    )
    def test_has_column(self, sql_028: str, column_decl: str) -> None:
        assert column_decl in sql_028

    def test_units_positive_check(self, sql_028: str) -> None:
        assert (
            "CONSTRAINT chk_dispensations_units CHECK (units_dispensed > 0)"
            in sql_028
        )

    def test_indexes(self, sql_028: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_disp_tenant" in sql_028
        assert "CREATE INDEX IF NOT EXISTS idx_disp_member" in sql_028
        assert "CREATE INDEX IF NOT EXISTS idx_disp_preparation" in sql_028
        assert "CREATE INDEX IF NOT EXISTS idx_disp_date" in sql_028


# ---------------------------------------------------------------------------
# Ordem de criacao (FKs internas)
# ---------------------------------------------------------------------------

class TestMigration028CreationOrder:
    def test_creation_order(self, sql_028: str) -> None:
        # FK chain: matrices -> seed_lots -> cultivation_batches -> plants/harvests
        #           harvests -> extractions -> preparations -> dispensations
        order = [
            "CREATE TABLE IF NOT EXISTS genetic_matrices",
            "CREATE TABLE IF NOT EXISTS seed_lots",
            "CREATE TABLE IF NOT EXISTS cultivation_batches",
            "CREATE TABLE IF NOT EXISTS plants",
            "CREATE TABLE IF NOT EXISTS harvests",
            "CREATE TABLE IF NOT EXISTS extractions",
            "CREATE TABLE IF NOT EXISTS preparations",
            "CREATE TABLE IF NOT EXISTS lab_analyses",
            "CREATE TABLE IF NOT EXISTS dispensations",
        ]
        positions = [sql_028.find(t) for t in order]
        assert all(p > 0 for p in positions), f"alguma tabela nao encontrada: {positions}"
        assert positions == sorted(positions), (
            f"ordem de criacao incorreta: {[(t, positions[i]) for i, t in enumerate(order)]}"
        )


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------

class TestMigration028Idempotency:
    def test_all_create_table_use_if_not_exists(self, sql_028_code: str) -> None:
        assert sql_028_code.count("CREATE TABLE") == sql_028_code.count(
            "CREATE TABLE IF NOT EXISTS"
        )

    def test_all_indexes_use_if_not_exists(self, sql_028_code: str) -> None:
        assert sql_028_code.count("CREATE INDEX") == sql_028_code.count(
            "CREATE INDEX IF NOT EXISTS"
        )

    def test_extension_uses_if_not_exists(self, sql_028_code: str) -> None:
        # Usa sql_028_code para nao contar mencoes em comentarios do cabecalho/rodape.
        assert "CREATE EXTENSION IF NOT EXISTS postgis" in sql_028_code
        count_total = sql_028_code.count("CREATE EXTENSION")
        count_idempotent = sql_028_code.count("CREATE EXTENSION IF NOT EXISTS")
        assert count_total == count_idempotent


# ---------------------------------------------------------------------------
# Escopo — F2.3 nao pode invadir outras fases
# ---------------------------------------------------------------------------

class TestMigration028Scope:
    @pytest.mark.parametrize(
        "out_of_scope_table",
        [
            # 029/030 (proximas migrations)
            "traceability_events",
            # Tabelas ja criadas em migrations anteriores
            "tenants",
            "patients",
            "prescriptions",
            "sops",
            "sop_versions",
            "association_members",
            # Futuras
            "adverse_events",
            "sandbox_projects",
            "blockchain_anchors",
        ],
    )
    def test_does_not_create_out_of_scope_tables(
        self, sql_028: str, out_of_scope_table: str
    ) -> None:
        assert f"CREATE TABLE {out_of_scope_table}" not in sql_028
        assert f"CREATE TABLE IF NOT EXISTS {out_of_scope_table}" not in sql_028

    def test_does_not_create_append_only_trigger(self, sql_028: str) -> None:
        # Trigger append-only para traceability_events fica em 030, nao aqui.
        assert "CREATE TRIGGER traceability_events_immutable" not in sql_028
        # Nao cria trigger nenhum nesta migration
        assert "CREATE TRIGGER" not in sql_028


# ---------------------------------------------------------------------------
# Down script
# ---------------------------------------------------------------------------

class TestMigration028Down:
    def test_has_header(self, sql_028_down: str) -> None:
        assert "Down migration 028" in sql_028_down
        assert "Traceability Schema Base" in sql_028_down

    @pytest.mark.parametrize(
        "table",
        [
            "dispensations",
            "lab_analyses",
            "preparations",
            "extractions",
            "harvests",
            "plants",
            "cultivation_batches",
            "seed_lots",
            "genetic_matrices",
        ],
    )
    def test_drops_every_created_table(self, sql_028_down: str, table: str) -> None:
        assert f"DROP TABLE IF EXISTS {table}" in sql_028_down

    def test_does_not_drop_postgis_extension(self, sql_028_down: str) -> None:
        # Extensao postgis pode ser compartilhada com outras migrations/features;
        # down nao deve droppar.
        assert "DROP EXTENSION" not in sql_028_down

    def test_reverse_order_leafs_before_roots(self, sql_028_down: str) -> None:
        # Validacao de que dependentes saem antes dos referenciados.
        order = [
            "DROP TABLE IF EXISTS dispensations",       # dep: preparations, members
            "DROP TABLE IF EXISTS preparations",        # dep: extractions
            "DROP TABLE IF EXISTS extractions",         # dep: harvests
            "DROP TABLE IF EXISTS harvests",            # dep: cultivation_batches
            "DROP TABLE IF EXISTS plants",              # dep: cultivation_batches
            "DROP TABLE IF EXISTS cultivation_batches", # dep: seed_lots, matrices
            "DROP TABLE IF EXISTS seed_lots",           # dep: matrices
            "DROP TABLE IF EXISTS genetic_matrices",    # root
        ]
        positions = [sql_028_down.find(d) for d in order]
        assert all(p > 0 for p in positions), f"drop ausente: {positions}"
        assert positions == sorted(positions), (
            "ordem de drop precisa ser reversa a criacao (folhas antes de raizes)"
        )

    def test_all_drops_use_if_exists(self, sql_028_down: str) -> None:
        code_lines = [
            line for line in sql_028_down.splitlines()
            if not line.lstrip().startswith("--")
        ]
        code = "\n".join(code_lines)
        assert code.count("DROP TABLE") == code.count("DROP TABLE IF EXISTS")

    def test_does_not_touch_preexisting_tables(self, sql_028_down: str) -> None:
        for preexisting in (
            "tenants", "users", "patients", "prescriptions",
            "association_members", "sop_versions", "sops",
        ):
            assert f"DROP TABLE IF EXISTS {preexisting}" not in sql_028_down
            assert f"DROP TABLE {preexisting}" not in sql_028_down
