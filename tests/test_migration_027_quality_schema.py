"""
Static validation of migration 027 (Quality Schema — F2.2 do SCC).

Valida por inspecao estatica do SQL que a migration:

1. Cria as seis tabelas previstas no doc 25 §§6.1-6.4 (sops, sop_versions,
   sop_trainings, sop_evidences, sop_deviations, capa_actions).
2. Resolve a FK circular entre sops e sop_versions (DO $$ com pg_constraint).
3. Cria a funcao `prevent_update_delete` e aplica trigger append-only em
   sop_evidences (doc §2.4 + §7.7).
4. Usa IF NOT EXISTS e DO $$ guards (idempotencia).
5. Respeita FKs externas para tenants(id) e users(id).
6. Nao toca tabelas fora do escopo.
7. Tem down-script paralelo que preserva a funcao compartilhada se ja estiver
   em uso por outros triggers (ex.: traceability_events da 030).

Validacao comportamental contra Postgres real fica para o passo de
roundtrip manual executado via scripts/run_migrations.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION_027 = MIGRATIONS_DIR / "027_quality_schema.sql"
MIGRATION_027_DOWN = MIGRATIONS_DIR / "down" / "027_quality_schema_down.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql_027() -> str:
    assert MIGRATION_027.exists(), f"migration ausente: {MIGRATION_027}"
    content = _read(MIGRATION_027)
    assert content.strip(), "migration 027 esta vazia"
    return content


@pytest.fixture(scope="module")
def sql_027_down() -> str:
    assert MIGRATION_027_DOWN.exists(), f"down script ausente: {MIGRATION_027_DOWN}"
    content = _read(MIGRATION_027_DOWN)
    assert content.strip(), "down 027 esta vazio"
    return content


@pytest.fixture(scope="module")
def sql_027_code(sql_027: str) -> str:
    """sql_027 sem linhas de comentario, para contagens idempotencia-safe."""
    return "\n".join(
        line for line in sql_027.splitlines()
        if not line.lstrip().startswith("--")
    )


# ---------------------------------------------------------------------------
# Structure & rastreabilidade
# ---------------------------------------------------------------------------

class TestMigration027Structure:
    def test_has_header(self, sql_027: str) -> None:
        assert "Migration 027" in sql_027
        assert "Quality Schema" in sql_027

    def test_references_backlog_and_doc25(self, sql_027: str) -> None:
        assert "F2.2" in sql_027
        assert "BACKLOG_SCC" in sql_027 or "doc 25" in sql_027 or "25_SCC_DATA_MODEL" in sql_027

    def test_references_doc25_sections(self, sql_027: str) -> None:
        for section in ("§6.1", "§6.2", "§6.3", "§6.4"):
            assert section in sql_027, f"falta referencia a {section}"

    def test_no_manual_schema_migrations_insert(self, sql_027: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql_027
        assert "UPDATE schema_migrations" not in sql_027


# ---------------------------------------------------------------------------
# Tabelas criadas
# ---------------------------------------------------------------------------

class TestMigration027Tables:
    @pytest.mark.parametrize(
        "table",
        [
            "sops",
            "sop_versions",
            "sop_trainings",
            "sop_evidences",
            "sop_deviations",
            "capa_actions",
        ],
    )
    def test_creates_table(self, sql_027: str, table: str) -> None:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql_027

    def test_creates_exactly_six_tables(self, sql_027_code: str) -> None:
        assert sql_027_code.count("CREATE TABLE IF NOT EXISTS") == 6
        assert sql_027_code.count("CREATE TABLE ") == sql_027_code.count(
            "CREATE TABLE IF NOT EXISTS"
        )


# ---------------------------------------------------------------------------
# sops (doc 25 §6.1)
# ---------------------------------------------------------------------------

class TestSops:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "id                 SERIAL PRIMARY KEY",
            "tenant_id          INT NOT NULL REFERENCES tenants(id)",
            "code               VARCHAR(64) NOT NULL",
            "title              VARCHAR(255) NOT NULL",
            "area               VARCHAR(64) NOT NULL",
            "current_version_id INT,",  # sem FK inline (circular)
            "is_active          BOOLEAN NOT NULL DEFAULT TRUE",
        ],
    )
    def test_has_column(self, sql_027: str, column_decl: str) -> None:
        assert column_decl in sql_027

    def test_unique_tenant_code(self, sql_027: str) -> None:
        assert "CONSTRAINT uq_sops_tenant_code UNIQUE (tenant_id, code)" in sql_027

    def test_indexes(self, sql_027: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_sops_tenant" in sql_027
        assert "CREATE INDEX IF NOT EXISTS idx_sops_area" in sql_027


# ---------------------------------------------------------------------------
# sop_versions (doc 25 §6.1)
# ---------------------------------------------------------------------------

class TestSopVersions:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "id              SERIAL PRIMARY KEY",
            "sop_id          INT NOT NULL REFERENCES sops(id)",
            "version_number  VARCHAR(32) NOT NULL",
            "content_uri     TEXT NOT NULL",
            "content_hash    CHAR(64) NOT NULL",
            "effective_from  DATE NOT NULL",
            "effective_until DATE",
            "approved_by     INT REFERENCES users(id)",
            "approved_at     TIMESTAMPTZ",
        ],
    )
    def test_has_column(self, sql_027: str, column_decl: str) -> None:
        assert column_decl in sql_027

    def test_unique_sop_version(self, sql_027: str) -> None:
        assert "CONSTRAINT uq_sop_versions UNIQUE (sop_id, version_number)" in sql_027

    def test_effective_order_check(self, sql_027: str) -> None:
        # Defensivo: effective_until >= effective_from.
        assert "CONSTRAINT chk_sop_versions_effective_order CHECK" in sql_027
        assert "effective_until IS NULL OR effective_until >= effective_from" in sql_027

    def test_index(self, sql_027: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_sop_versions_sop" in sql_027


# ---------------------------------------------------------------------------
# FK circular resolvida
# ---------------------------------------------------------------------------

class TestCircularFk:
    def test_sops_created_without_inline_fk_to_versions(self, sql_027: str) -> None:
        # sops declara `current_version_id INT` SEM `REFERENCES sop_versions(id)` inline.
        assert "current_version_id INT,  -- FK adicionada apos sop_versions existir" in sql_027

    def test_alter_sops_adds_fk_after_versions(self, sql_027: str) -> None:
        # FK circular resolvida por ALTER TABLE, em DO $$ com pg_constraint guard.
        assert "ADD CONSTRAINT fk_sops_current_version" in sql_027
        assert "FOREIGN KEY (current_version_id) REFERENCES sop_versions(id)" in sql_027
        assert "WHERE conname = 'fk_sops_current_version'" in sql_027

    def test_alter_comes_after_both_tables(self, sql_027: str) -> None:
        # Ordem: CREATE sops -> CREATE sop_versions -> ALTER sops ADD FK.
        pos_sops = sql_027.find("CREATE TABLE IF NOT EXISTS sops")
        pos_versions = sql_027.find("CREATE TABLE IF NOT EXISTS sop_versions")
        pos_alter = sql_027.find("ADD CONSTRAINT fk_sops_current_version")
        assert 0 < pos_sops < pos_versions < pos_alter, (
            "ALTER TABLE ADD FK circular precisa vir APOS ambas as tabelas"
        )


# ---------------------------------------------------------------------------
# sop_trainings (doc 25 §6.2)
# ---------------------------------------------------------------------------

class TestSopTrainings:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "id             SERIAL PRIMARY KEY",
            "sop_version_id INT NOT NULL REFERENCES sop_versions(id)",
            "user_id        INT NOT NULL REFERENCES users(id)",
            "trained_at     TIMESTAMPTZ NOT NULL",
            "evidence_uri   TEXT",
            "evidence_hash  CHAR(64)",
        ],
    )
    def test_has_column(self, sql_027: str, column_decl: str) -> None:
        assert column_decl in sql_027

    def test_unique_version_user(self, sql_027: str) -> None:
        # Um usuario so pode ter 1 treinamento registrado por versao de SOP.
        assert "CONSTRAINT uq_sop_trainings UNIQUE (sop_version_id, user_id)" in sql_027


# ---------------------------------------------------------------------------
# sop_evidences (doc 25 §6.3) — APPEND-ONLY
# ---------------------------------------------------------------------------

class TestSopEvidences:
    def test_bigserial_pk(self, sql_027: str) -> None:
        # Escala alta -> BIGSERIAL, nao SERIAL.
        assert "id                 BIGSERIAL PRIMARY KEY" in sql_027

    @pytest.mark.parametrize(
        "column_decl",
        [
            "tenant_id          INT NOT NULL REFERENCES tenants(id)",
            "sop_version_id     INT NOT NULL REFERENCES sop_versions(id)",
            "executed_by        INT REFERENCES users(id)",
            "execution_context  JSONB NOT NULL",
            "related_event_type VARCHAR(64)",
            "related_event_id   BIGINT",
            "chain_id           VARCHAR(128) NOT NULL",
            "chain_sequence     BIGINT NOT NULL",
            "event_hash         CHAR(64) NOT NULL",
            "previous_hash      CHAR(64)",
        ],
    )
    def test_has_column(self, sql_027: str, column_decl: str) -> None:
        assert column_decl in sql_027

    def test_unique_chain_sequence(self, sql_027: str) -> None:
        assert (
            "CONSTRAINT uq_sop_evidences_chain UNIQUE (chain_id, chain_sequence)"
            in sql_027
        )

    def test_chain_sequence_check(self, sql_027: str) -> None:
        # Sequencia comeca em 1; 0 ou negativos nao fazem sentido.
        assert (
            "CONSTRAINT chk_sop_evidences_sequence CHECK (chain_sequence >= 1)"
            in sql_027
        )

    def test_indexes(self, sql_027: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_sop_ev_tenant" in sql_027
        assert "CREATE INDEX IF NOT EXISTS idx_sop_ev_version" in sql_027
        assert "CREATE INDEX IF NOT EXISTS idx_sop_ev_created" in sql_027


# ---------------------------------------------------------------------------
# Protection trigger append-only (doc 25 §2.4 + §7.7)
# ---------------------------------------------------------------------------

class TestAppendOnlyTrigger:
    def test_creates_shared_function(self, sql_027: str) -> None:
        # prevent_update_delete e compartilhada com traceability_events (030).
        assert "CREATE OR REPLACE FUNCTION prevent_update_delete()" in sql_027
        assert "RETURNS TRIGGER" in sql_027
        assert "LANGUAGE plpgsql" in sql_027

    def test_function_raises_exception(self, sql_027: str) -> None:
        assert "RAISE EXCEPTION" in sql_027
        assert "append-only" in sql_027.lower()
        assert "TG_TABLE_NAME" in sql_027

    def test_applies_trigger_to_sop_evidences(self, sql_027: str) -> None:
        assert "CREATE TRIGGER sop_evidences_immutable" in sql_027
        assert "BEFORE UPDATE OR DELETE ON sop_evidences" in sql_027
        assert "EXECUTE FUNCTION prevent_update_delete()" in sql_027

    def test_trigger_guarded_by_pg_trigger(self, sql_027: str) -> None:
        # Trigger idempotencia via DO $$ + pg_trigger check.
        assert "WHERE tgname = 'sop_evidences_immutable'" in sql_027
        assert "FROM pg_trigger" in sql_027

    def test_trigger_comes_after_sop_evidences(self, sql_027: str) -> None:
        pos_table = sql_027.find("CREATE TABLE IF NOT EXISTS sop_evidences")
        pos_trigger = sql_027.find("CREATE TRIGGER sop_evidences_immutable")
        assert 0 < pos_table < pos_trigger, (
            "trigger append-only precisa vir APOS sop_evidences existir"
        )


# ---------------------------------------------------------------------------
# sop_deviations (doc 25 §6.4)
# ---------------------------------------------------------------------------

class TestSopDeviations:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "id             SERIAL PRIMARY KEY",
            "tenant_id      INT NOT NULL REFERENCES tenants(id)",
            "sop_version_id INT NOT NULL REFERENCES sop_versions(id)",
            "deviation_date TIMESTAMPTZ NOT NULL",
            "severity       VARCHAR(16) NOT NULL",
            "description    TEXT NOT NULL",
            "detected_by    INT REFERENCES users(id)",
            "status         VARCHAR(32) NOT NULL",
        ],
    )
    def test_has_column(self, sql_027: str, column_decl: str) -> None:
        assert column_decl in sql_027

    def test_severity_check_whitelist(self, sql_027: str) -> None:
        assert "CONSTRAINT chk_sop_deviations_severity CHECK" in sql_027
        for sev in ("'low'", "'medium'", "'high'", "'critical'"):
            assert sev in sql_027, f"falta severity: {sev}"

    def test_status_check_whitelist(self, sql_027: str) -> None:
        assert "CONSTRAINT chk_sop_deviations_status CHECK" in sql_027
        for st in ("'open'", "'investigating'", "'capa_pending'", "'resolved'", "'closed'"):
            assert st in sql_027, f"falta status: {st}"

    def test_indexes(self, sql_027: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_sop_dev_tenant" in sql_027
        assert "CREATE INDEX IF NOT EXISTS idx_sop_dev_version" in sql_027
        assert "CREATE INDEX IF NOT EXISTS idx_sop_dev_status" in sql_027


# ---------------------------------------------------------------------------
# capa_actions (doc 25 §6.4)
# ---------------------------------------------------------------------------

class TestCapaActions:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "id                  SERIAL PRIMARY KEY",
            "deviation_id        INT NOT NULL REFERENCES sop_deviations(id)",
            "action_type         VARCHAR(16) NOT NULL",
            "description         TEXT NOT NULL",
            "responsible         INT REFERENCES users(id)",
            "due_date            DATE NOT NULL",
            "completed_at        TIMESTAMPTZ",
            "effectiveness_check TEXT",
        ],
    )
    def test_has_column(self, sql_027: str, column_decl: str) -> None:
        assert column_decl in sql_027

    def test_action_type_check_whitelist(self, sql_027: str) -> None:
        assert "CONSTRAINT chk_capa_action_type CHECK" in sql_027
        assert "'corrective'" in sql_027
        assert "'preventive'" in sql_027

    def test_completion_order_check(self, sql_027: str) -> None:
        # Defensivo: completed_at nao pode preceder created_at.
        assert "CONSTRAINT chk_capa_completion_order CHECK" in sql_027
        assert "completed_at IS NULL OR completed_at >= created_at" in sql_027

    def test_indexes(self, sql_027: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_capa_deviation" in sql_027
        assert "CREATE INDEX IF NOT EXISTS idx_capa_due_date" in sql_027


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------

class TestMigration027Idempotency:
    def test_all_create_table_use_if_not_exists(self, sql_027_code: str) -> None:
        assert sql_027_code.count("CREATE TABLE") == sql_027_code.count(
            "CREATE TABLE IF NOT EXISTS"
        )

    def test_all_indexes_use_if_not_exists(self, sql_027_code: str) -> None:
        assert sql_027_code.count("CREATE INDEX") == sql_027_code.count(
            "CREATE INDEX IF NOT EXISTS"
        )

    def test_function_uses_or_replace(self, sql_027: str) -> None:
        # prevent_update_delete e CREATE OR REPLACE -> seguro para re-execucao.
        assert "CREATE OR REPLACE FUNCTION" in sql_027
        assert "CREATE FUNCTION prevent_update_delete" not in sql_027

    def test_alter_fk_guarded_by_pg_constraint(self, sql_027: str) -> None:
        # fk_sops_current_version em DO $$ com pg_constraint guard.
        assert "pg_constraint" in sql_027
        assert "fk_sops_current_version" in sql_027


# ---------------------------------------------------------------------------
# Escopo
# ---------------------------------------------------------------------------

class TestMigration027Scope:
    @pytest.mark.parametrize(
        "out_of_scope_table",
        [
            # Ja criadas em migrations anteriores
            "tenants",
            "associations",
            "institutional_documents",
            "technical_responsibles",
            "technical_operational_capacity",
            "association_members",
            "member_consents",
            # Futuras
            "traceability_events",
            "genetic_matrices",
            "adverse_events",
            "sandbox_projects",
        ],
    )
    def test_does_not_create_out_of_scope_tables(
        self, sql_027: str, out_of_scope_table: str
    ) -> None:
        assert f"CREATE TABLE {out_of_scope_table}" not in sql_027
        assert f"CREATE TABLE IF NOT EXISTS {out_of_scope_table}" not in sql_027

    def test_does_not_create_traceability_trigger(self, sql_027: str) -> None:
        # traceability_events_immutable e da migration 030, nao daqui.
        assert "CREATE TRIGGER traceability_events_immutable" not in sql_027


# ---------------------------------------------------------------------------
# Down script
# ---------------------------------------------------------------------------

class TestMigration027Down:
    def test_has_header(self, sql_027_down: str) -> None:
        assert "Down migration 027" in sql_027_down
        assert "Quality Schema" in sql_027_down

    @pytest.mark.parametrize(
        "table",
        [
            "capa_actions",
            "sop_deviations",
            "sop_evidences",
            "sop_trainings",
            "sop_versions",
            "sops",
        ],
    )
    def test_drops_every_created_table(self, sql_027_down: str, table: str) -> None:
        assert f"DROP TABLE IF EXISTS {table}" in sql_027_down

    def test_drops_circular_fk_before_sop_versions(self, sql_027_down: str) -> None:
        # fk_sops_current_version precisa ser dropado ANTES de dropar sop_versions.
        pos_drop_fk = sql_027_down.find(
            "DROP CONSTRAINT IF EXISTS fk_sops_current_version"
        )
        pos_drop_versions = sql_027_down.find("DROP TABLE IF EXISTS sop_versions")
        assert 0 < pos_drop_fk < pos_drop_versions, (
            "FK circular precisa ser dropada antes de sop_versions"
        )

    def test_drops_trigger_explicitly(self, sql_027_down: str) -> None:
        # Drop da tabela ja dropa o trigger em cascata, mas drop explicito
        # torna o rollback mais auditavel.
        assert "DROP TRIGGER IF EXISTS sop_evidences_immutable" in sql_027_down

    def test_conditional_drop_of_shared_function(self, sql_027_down: str) -> None:
        # prevent_update_delete e compartilhada com 030. Drop condicional via
        # DO $$ que checa se ha outros triggers usando a funcao.
        assert "prevent_update_delete" in sql_027_down
        assert "pg_trigger" in sql_027_down
        assert "pg_proc" in sql_027_down
        assert "DROP FUNCTION IF EXISTS prevent_update_delete" in sql_027_down

    def test_all_drops_use_if_exists(self, sql_027_down: str) -> None:
        code_lines = [
            line for line in sql_027_down.splitlines()
            if not line.lstrip().startswith("--")
        ]
        code = "\n".join(code_lines)
        assert code.count("DROP TABLE") == code.count("DROP TABLE IF EXISTS")
        assert code.count("DROP TRIGGER") == code.count("DROP TRIGGER IF EXISTS")

    def test_does_not_touch_preexisting_tables(self, sql_027_down: str) -> None:
        for preexisting in (
            "tenants", "users", "association_members", "member_consents",
            "associations", "institutional_documents",
        ):
            assert f"DROP TABLE IF EXISTS {preexisting}" not in sql_027_down
            assert f"DROP TABLE {preexisting}" not in sql_027_down
