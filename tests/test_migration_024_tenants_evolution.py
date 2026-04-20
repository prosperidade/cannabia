"""
Static validation of migration 024 (Tenants Evolution — F1.1 do SCC).

Valida por inspecao estatica do SQL que a migration:

1. Adiciona exatamente as colunas previstas no doc 25 §4.1.
2. Usa CHECK constraints com whitelists canonicas.
3. Faz backfill defensivo antes de SET NOT NULL.
4. Cria indexes conforme doc 25.
5. E idempotente (IF NOT EXISTS em ADD COLUMN e CREATE INDEX, DO $$
   com verificacao em pg_constraint para constraints).
6. Preserva retrocompatibilidade — nao dropa colunas existentes
   (tenant_type_id, billing_plan, display_name, status).

Validacao comportamental contra Postgres real fica para smoke tests
executados via scripts/setup_local.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION_024 = MIGRATIONS_DIR / "024_tenants_evolution.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql_024() -> str:
    assert MIGRATION_024.exists(), f"migration ausente: {MIGRATION_024}"
    content = _read(MIGRATION_024)
    assert content.strip(), "migration 024 esta vazia"
    return content


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

class TestMigration024Structure:
    def test_has_header(self, sql_024: str) -> None:
        assert "Migration 024" in sql_024
        assert "Tenants Evolution" in sql_024

    def test_references_scc_sources(self, sql_024: str) -> None:
        # Rastreabilidade: comenta de onde vem o escopo (F1.1 e doc 25 §4.1)
        assert "F1.1" in sql_024
        assert "BACKLOG_SCC" in sql_024 or "doc 25" in sql_024 or "25_SCC_DATA_MODEL" in sql_024

    def test_no_manual_schema_migrations_insert(self, sql_024: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql_024
        assert "UPDATE schema_migrations" not in sql_024


# ---------------------------------------------------------------------------
# Colunas adicionadas
# ---------------------------------------------------------------------------

class TestMigration024Columns:
    @pytest.mark.parametrize(
        "column",
        [
            "tenant_type",
            "trade_name",
            "cnpj",
            "incorporation_date",
            "plan_tier",
            "whitelabel_config",
            "is_active",
        ],
    )
    def test_adds_column(self, sql_024: str, column: str) -> None:
        # Cada coluna deve ter seu ADD COLUMN IF NOT EXISTS dedicado.
        assert f"ADD COLUMN IF NOT EXISTS {column}" in sql_024

    def test_whitelabel_config_is_jsonb(self, sql_024: str) -> None:
        assert "whitelabel_config JSONB" in sql_024

    def test_cnpj_is_varchar_14(self, sql_024: str) -> None:
        assert "cnpj VARCHAR(14)" in sql_024

    def test_incorporation_date_is_date(self, sql_024: str) -> None:
        assert "incorporation_date DATE" in sql_024

    def test_is_active_is_generated_stored(self, sql_024: str) -> None:
        # Coluna gerada ancorada em `status`, STORED (persistida)
        assert "is_active BOOLEAN" in sql_024
        assert "GENERATED ALWAYS AS (status = 'active') STORED" in sql_024


# ---------------------------------------------------------------------------
# CHECK constraints
# ---------------------------------------------------------------------------

class TestMigration024Checks:
    def test_tenant_type_check_whitelist(self, sql_024: str) -> None:
        # tenant_type aceita exatamente os 3 slugs canonicos existentes em tenant_types
        assert "chk_tenants_type" in sql_024
        assert "'clinic'" in sql_024 and "'association'" in sql_024 and "'doctor'" in sql_024
        # CHECK envolve os tres — procura a expressao literal
        assert "CHECK (tenant_type IN ('clinic', 'association', 'doctor'))" in sql_024

    def test_plan_tier_check_whitelist(self, sql_024: str) -> None:
        assert "chk_tenants_plan_tier" in sql_024
        assert (
            "CHECK (plan_tier IN ('basic', 'pro', 'premium', 'sandbox_ready'))"
            in sql_024
        )

    def test_sandbox_ready_is_a_valid_plan_tier(self, sql_024: str) -> None:
        # Valor reservado para o SCC — deve estar no whitelist desde o dia 1
        assert "'sandbox_ready'" in sql_024

    def test_constraints_wrapped_in_do_blocks(self, sql_024: str) -> None:
        # Ambos CHECKs sao adicionados dentro de DO $$ que consulta pg_constraint
        # para permitir re-execucao sem erro de "constraint already exists".
        assert sql_024.count("DO $$") >= 2
        assert sql_024.count("pg_constraint") >= 2
        assert sql_024.count("ADD CONSTRAINT chk_tenants_") >= 2


# ---------------------------------------------------------------------------
# Backfill — precedencia correta e fallback defensivo
# ---------------------------------------------------------------------------

class TestMigration024Backfill:
    def test_tenant_type_backfilled_from_tenant_types(self, sql_024: str) -> None:
        # Backfill usa JOIN com tenant_types.slug antes do SET NOT NULL
        assert "FROM tenant_types tt" in sql_024
        assert "t.tenant_type_id = tt.id" in sql_024

    def test_tenant_type_defensive_fallback_to_clinic(self, sql_024: str) -> None:
        # Se um tenant_type_id nao resolver para um slug valido, assume 'clinic'.
        # Evita falha no SET NOT NULL por dados historicos.
        assert "WHERE tenant_type IS NULL" in sql_024
        assert "SET tenant_type = 'clinic'" in sql_024

    def test_trade_name_backfilled_from_display_name(self, sql_024: str) -> None:
        assert "SET trade_name = display_name" in sql_024
        assert "WHERE trade_name IS NULL" in sql_024

    def test_plan_tier_maps_starter_to_basic(self, sql_024: str) -> None:
        # billing_plan='starter' (legado) precisa mapear para plan_tier='basic'
        # porque 'starter' nao esta no CHECK whitelist do SCC.
        assert "WHEN billing_plan = 'starter' THEN 'basic'" in sql_024

    def test_plan_tier_preserves_valid_scc_values(self, sql_024: str) -> None:
        # Se billing_plan ja e um valor valido do SCC, preserva-se.
        assert "billing_plan IN ('basic', 'pro', 'premium', 'sandbox_ready')" in sql_024

    def test_plan_tier_defensive_fallback(self, sql_024: str) -> None:
        # Qualquer outro valor inesperado -> 'basic' (nao quebra CHECK)
        assert "ELSE 'basic'" in sql_024

    def test_not_null_comes_after_backfill(self, sql_024: str) -> None:
        # tenant_type: backfill antes do SET NOT NULL
        backfill_pos = sql_024.find("UPDATE tenants SET tenant_type = 'clinic'")
        not_null_pos = sql_024.find("ALTER COLUMN tenant_type SET NOT NULL")
        assert 0 < backfill_pos < not_null_pos, (
            "SET NOT NULL em tenant_type deve vir DEPOIS do backfill defensivo"
        )

        # plan_tier: backfill antes do SET NOT NULL
        backfill_pos = sql_024.find("WHEN billing_plan = 'starter'")
        not_null_pos = sql_024.find("ALTER COLUMN plan_tier SET NOT NULL")
        assert 0 < backfill_pos < not_null_pos, (
            "SET NOT NULL em plan_tier deve vir DEPOIS do backfill"
        )


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------

class TestMigration024Indexes:
    def test_unique_cnpj_partial(self, sql_024: str) -> None:
        assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_tenants_cnpj" in sql_024
        # Partial: ignora NULL e string vazia
        assert "WHERE cnpj IS NOT NULL" in sql_024
        assert "cnpj <> ''" in sql_024

    def test_idx_tenant_type(self, sql_024: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_tenants_type" in sql_024

    def test_idx_plan_tier(self, sql_024: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_tenants_plan_tier" in sql_024


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------

class TestMigration024Idempotency:
    def test_all_add_column_use_if_not_exists(self, sql_024: str) -> None:
        # Ignora linhas de comentario (que podem mencionar "ADD COLUMN" em prosa)
        # e conta somente ocorrencias em linhas de SQL executavel.
        code_lines = [
            line for line in sql_024.splitlines()
            if not line.lstrip().startswith("--")
        ]
        code = "\n".join(code_lines)
        total_add_column = code.count("ADD COLUMN")
        idempotent = code.count("ADD COLUMN IF NOT EXISTS")
        assert total_add_column == idempotent, (
            f"ADD COLUMN sem IF NOT EXISTS detectado: "
            f"{total_add_column - idempotent} ocorrencia(s) nao-idempotente(s)"
        )

    def test_all_indexes_use_if_not_exists(self, sql_024: str) -> None:
        assert sql_024.count("CREATE INDEX") == sql_024.count("CREATE INDEX IF NOT EXISTS")
        assert sql_024.count("CREATE UNIQUE INDEX") == sql_024.count(
            "CREATE UNIQUE INDEX IF NOT EXISTS"
        )


# ---------------------------------------------------------------------------
# Retrocompatibilidade — nada que ja existia pode ser dropado
# ---------------------------------------------------------------------------

class TestMigration024BackwardsCompat:
    @pytest.mark.parametrize(
        "legacy_column",
        [
            "tenant_type_id",      # FK para tenant_types
            "billing_plan",        # adicionado em 020
            "display_name",        # original de 004
            "status",              # original de 004
            "legacy_clinic_id",    # ponte para clinics legado
            "slug",                # original de 004
        ],
    )
    def test_does_not_drop_legacy_column(self, sql_024: str, legacy_column: str) -> None:
        # Pode MENCIONAR (UPDATE ... SET plan_tier = billing_plan, por exemplo),
        # mas nao pode dropar.
        assert f"DROP COLUMN {legacy_column}" not in sql_024
        assert f"DROP COLUMN IF EXISTS {legacy_column}" not in sql_024

    def test_does_not_drop_tenants_table(self, sql_024: str) -> None:
        assert "DROP TABLE" not in sql_024

    def test_does_not_touch_other_migrations_domain(self, sql_024: str) -> None:
        # Sanity: F1.1 e so sobre tenants. Nao pode criar tabelas do SCC
        # que pertencem a migrations futuras (025+).
        scc_tables_futuras = [
            "associations",
            "technical_responsibles",
            "institutional_documents",
            "association_members",
            "member_consents",
            "sops",
            "traceability_events",
            "adverse_events",
            "sandbox_projects",
            "blockchain_anchors",
        ]
        for table in scc_tables_futuras:
            # Permitido em comentarios, mas nao em CREATE TABLE
            assert f"CREATE TABLE {table}" not in sql_024
            assert f"CREATE TABLE IF NOT EXISTS {table}" not in sql_024
