"""
Static validation of migrations 022 and 023 (Integrity Hardening +
Timestamp Standardization).

These migrations are DDL-heavy and idempotent by design. In ausencia de
fixtures de DB dedicadas ao ciclo de schema (o test_migrations.py cobre
apenas o runner), validamos aqui por inspecao estatica que cada migration:

1. Existe e nao esta vazia.
2. Carrega os blocos DDL pretendidos (UNIQUE, FK, CHECK, GIN, etc.).
3. Usa padroes idempotentes (IF NOT EXISTS, DO $$ com verificacoes em
   information_schema antes de alterar o schema).
4. Respeita o contrato com o runner (sem INSERT manual em
   schema_migrations — a versao e gravada pelo runner).

Validacao de comportamento contra um Postgres real fica para smoke tests
de integracao executados pelo scripts/setup_local.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

MIGRATION_022 = MIGRATIONS_DIR / "022_integrity_hardening.sql"
MIGRATION_023 = MIGRATIONS_DIR / "023_timestamp_standardization.sql"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql_022() -> str:
    assert MIGRATION_022.exists(), f"migration ausente: {MIGRATION_022}"
    content = _read(MIGRATION_022)
    assert content.strip(), "migration 022 esta vazia"
    return content


@pytest.fixture(scope="module")
def sql_023() -> str:
    assert MIGRATION_023.exists(), f"migration ausente: {MIGRATION_023}"
    content = _read(MIGRATION_023)
    assert content.strip(), "migration 023 esta vazia"
    return content


# ---------------------------------------------------------------------------
# Migration 022 — Integrity Hardening
# ---------------------------------------------------------------------------

class TestMigration022Structure:
    """Validacao de estrutura geral da 022."""

    def test_has_header(self, sql_022: str) -> None:
        assert "Migration 022" in sql_022
        assert "Integrity Hardening" in sql_022

    def test_no_manual_schema_migrations_insert(self, sql_022: str) -> None:
        # O runner cuida do tracking; INSERTs manuais foram removidos em
        # progresso10. Garantimos que a 022 nao reintroduz esse padrao.
        lowered = sql_022.lower()
        assert "insert into schema_migrations" not in lowered


class TestMigration022Uniqueness:
    """Verifica os indices UNIQUE criados."""

    def test_unique_email_on_users(self, sql_022: str) -> None:
        assert "uq_users_email_lower" in sql_022
        assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower" in sql_022
        assert "LOWER(email)" in sql_022
        # Partial: nao pode bloquear emails NULL/vazios de rows antigas
        assert "WHERE email IS NOT NULL" in sql_022

    def test_unique_triage_links_token_hash(self, sql_022: str) -> None:
        assert "uq_triage_links_token_hash" in sql_022
        assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_triage_links_token_hash" in sql_022

    def test_drops_old_non_unique_triage_links_index(self, sql_022: str) -> None:
        # O index nao-unico de 018 tem que ser removido para nao duplicar o UNIQUE
        assert "DROP INDEX IF EXISTS idx_triage_links_token_hash" in sql_022


class TestMigration022ForeignKey:
    """FK em patients.user_id -> users(id)."""

    def test_fk_declared(self, sql_022: str) -> None:
        assert "fk_patients_user" in sql_022
        assert "REFERENCES users(id)" in sql_022
        assert "ON DELETE SET NULL" in sql_022

    def test_fk_wrapped_in_idempotency_check(self, sql_022: str) -> None:
        # FK so e criada se ainda nao existir
        assert "information_schema.table_constraints" in sql_022
        assert "constraint_name = 'fk_patients_user'" in sql_022

    def test_fk_cleans_orphan_user_ids_first(self, sql_022: str) -> None:
        # Evita falha da FK em ambientes com user_ids historicos quebrados
        assert "UPDATE patients" in sql_022
        assert "SET user_id = NULL" in sql_022


class TestMigration022ChecksPatients:
    def test_check_constraint_added(self, sql_022: str) -> None:
        assert "chk_patients_status" in sql_022

    def test_whitelist_covers_observed_seed_values(self, sql_022: str) -> None:
        # Valores presentes no scripts/seed_comprehensive.py
        for value in ("ativo", "inativo", "em_tratamento", "aguardando_consulta"):
            assert f"'{value}'" in sql_022, f"status {value!r} ausente do CHECK"

    def test_whitelist_has_archived_for_lifecycle(self, sql_022: str) -> None:
        assert "'arquivado'" in sql_022

    def test_pre_normalizes_unknown_status_to_active(self, sql_022: str) -> None:
        # Linha chave: qualquer status fora do whitelist vira 'ativo' antes do CHECK
        assert "UPDATE patients" in sql_022
        # Garantimos a presenca da clausula de fallback
        assert "status IS NULL" in sql_022 or "status NOT IN" in sql_022


class TestMigration022ChecksTreatmentPlans:
    def test_check_constraint_added(self, sql_022: str) -> None:
        assert "chk_treatment_plans_status" in sql_022

    def test_allows_null_for_pre014_rows(self, sql_022: str) -> None:
        # A coluna foi adicionada apenas em 014; rows mais antigas teriam NULL.
        # O CHECK precisa aceitar NULL explicitamente.
        assert "status IS NULL" in sql_022

    def test_whitelist_values(self, sql_022: str) -> None:
        for value in ("ativo", "inativo", "suspenso", "concluido", "arquivado"):
            assert f"'{value}'" in sql_022


class TestMigration022ChecksAnamnesisReports:
    def test_check_constraint_added(self, sql_022: str) -> None:
        assert "chk_anamnesis_reports_status" in sql_022

    def test_whitelist_matches_repository_usage(self, sql_022: str) -> None:
        # 'pendente' e 'revisado' estao no repositorio e no seed;
        # 'arquivado' e 'cancelado' compõem o ciclo de vida esperado.
        for value in ("pendente", "revisado", "arquivado", "cancelado"):
            assert f"'{value}'" in sql_022


class TestMigration022GinIndexes:
    def test_gin_on_input_payload(self, sql_022: str) -> None:
        assert "idx_ai_audit_logs_input_payload_gin" in sql_022
        assert "USING GIN (input_payload)" in sql_022

    def test_gin_on_output_payload_with_partial_not_null(self, sql_022: str) -> None:
        assert "idx_ai_audit_logs_output_payload_gin" in sql_022
        assert "USING GIN (output_payload)" in sql_022
        # Output payload e opcional; o indice parcial economiza espaco.
        assert "WHERE output_payload IS NOT NULL" in sql_022


class TestMigration022Idempotency:
    """A migration precisa ser segura para reexecucao."""

    def test_all_indexes_use_if_not_exists(self, sql_022: str) -> None:
        # Todo CREATE INDEX/UNIQUE INDEX deve ser condicional
        for line in sql_022.splitlines():
            stripped = line.strip().upper()
            if stripped.startswith("CREATE INDEX") or stripped.startswith("CREATE UNIQUE INDEX"):
                assert "IF NOT EXISTS" in line, (
                    f"indice sem IF NOT EXISTS viola idempotencia: {line}"
                )

    def test_fk_and_checks_wrapped_in_do_blocks(self, sql_022: str) -> None:
        # Contagem minima de DO $$ ... $$ para as 4 alteracoes condicionais:
        # FK patients.user_id + 3 CHECKs (patients/treatment_plans/anamnesis_reports)
        do_block_count = sql_022.count("DO $$")
        assert do_block_count >= 4, (
            f"esperado >=4 DO $$ blocos, encontrado {do_block_count}"
        )


# ---------------------------------------------------------------------------
# Migration 023 — Timestamp Standardization
# ---------------------------------------------------------------------------

class TestMigration023Structure:
    def test_has_header(self, sql_023: str) -> None:
        assert "Migration 023" in sql_023
        assert "Timestamp Standardization" in sql_023

    def test_no_manual_schema_migrations_insert(self, sql_023: str) -> None:
        lowered = sql_023.lower()
        assert "insert into schema_migrations" not in lowered

    def test_uses_utc_as_conversion_reference(self, sql_023: str) -> None:
        # O USING ... AT TIME ZONE 'UTC' e o ponto critico para nao shiftar
        # os timestamps historicos durante a conversao.
        assert "AT TIME ZONE ''UTC''" in sql_023


class TestMigration023Targets:
    """Garante que as colunas de 001 e 003 foram incluidas."""

    # Colunas TIMESTAMP definidas em migrations/001_initial_schema.sql
    # e migrations/003_anamnesis_reports.sql que este migration converte.
    LEGACY_TARGETS = {
        ("clinics", "created_at"),
        ("clinics", "updated_at"),
        ("patients", "created_at"),
        ("ai_prompt_versions", "created_at"),
        ("users", "created_at"),
        ("user_clinics", "created_at"),
        ("appointments", "appointment_date"),
        ("appointments", "created_at"),
        ("message_status_updates", "created_at"),
        ("ai_audit_logs", "created_at"),
        ("alerts", "alert_time"),
        ("alerts", "created_at"),
        ("medical_history", "created_at"),
        ("monitoring", "created_at"),
        ("scientific_references", "created_at"),
        ("treatment_plans", "created_at"),
        ("anamnesis_reports", "created_at"),
        ("anamnesis_reports", "updated_at"),
    }

    def test_all_legacy_targets_mentioned(self, sql_023: str) -> None:
        for table, col in self.LEGACY_TARGETS:
            # Os pares [table, col] aparecem dentro de arrays de TEXT[][]
            pair = f"['{table}',"
            assert pair in sql_023, f"alvo ausente: {table}.{col}"
            # A coluna precisa estar presente em algum lugar tambem
            assert col in sql_023, f"coluna ausente no script: {table}.{col}"


class TestMigration023Idempotency:
    def test_checks_current_type_before_converting(self, sql_023: str) -> None:
        # O bloco de conversao so mexe se current_type for 'timestamp without time zone'
        assert "timestamp without time zone" in sql_023
        assert "timestamp with time zone" in sql_023

    def test_skips_missing_tables_gracefully(self, sql_023: str) -> None:
        # Ambientes parciais nao devem quebrar
        assert "information_schema.tables" in sql_023
        assert "RAISE NOTICE" in sql_023 or "CONTINUE" in sql_023

    def test_default_reset_block_guards_existence(self, sql_023: str) -> None:
        # O bloco que redefine DEFAULT NOW() pula colunas ausentes
        assert "SET DEFAULT NOW()" in sql_023
        # Antes de alterar o default, verifica se a coluna existe
        assert "information_schema.columns" in sql_023


class TestMigration023ViewHandling:
    """A view `clinic_members` (criada em 014) depende de
    `user_clinics.created_at`. Sem drop+recreate explicito, ALTER COLUMN
    TYPE falha com 'regra _RETURN em visao depende da coluna'. Descoberto
    em 2026-04-19 ao aplicar em Postgres local."""

    def test_drops_clinic_members_view_before_alter(self, sql_023: str) -> None:
        assert "DROP VIEW IF EXISTS clinic_members" in sql_023

    def test_recreates_clinic_members_view(self, sql_023: str) -> None:
        assert "CREATE OR REPLACE VIEW clinic_members" in sql_023
        # A definicao recriada deve preservar os campos originais de 014
        assert "user_id" in sql_023
        assert "clinic_id" in sql_023
        assert "role AS clinic_role" in sql_023
        assert "is_default" in sql_023
        assert "FROM user_clinics" in sql_023

    def test_drop_precedes_alter_loop(self, sql_023: str) -> None:
        drop_pos = sql_023.find("DROP VIEW IF EXISTS clinic_members")
        alter_pos = sql_023.find("ALTER COLUMN %I TYPE TIMESTAMPTZ")
        assert drop_pos != -1 and alter_pos != -1
        assert drop_pos < alter_pos, "DROP VIEW precisa vir antes do ALTER COLUMN"

    def test_recreate_follows_alter_loop(self, sql_023: str) -> None:
        alter_pos = sql_023.find("ALTER COLUMN %I TYPE TIMESTAMPTZ")
        recreate_pos = sql_023.find("CREATE OR REPLACE VIEW clinic_members")
        assert alter_pos != -1 and recreate_pos != -1
        assert alter_pos < recreate_pos, "CREATE VIEW precisa vir depois do ALTER COLUMN"


# ---------------------------------------------------------------------------
# Sanity cross-migration — nenhuma colisao de nomenclatura
# ---------------------------------------------------------------------------

def test_022_and_023_files_have_distinct_versions(sql_022: str, sql_023: str) -> None:
    assert "Migration 022" in sql_022
    assert "Migration 023" in sql_023
    assert "Migration 023" not in sql_022
    assert "Migration 022" not in sql_023


def test_neither_migration_redefines_scc_identifiers() -> None:
    """As 022/023 saneiam a base; nao podem introduzir nenhum nome
    reservado para a serie SCC (024-036)."""
    for path in (MIGRATION_022, MIGRATION_023):
        content = _read(path).lower()
        # Nomes tipicos que serao introduzidos pela serie SCC em 024+
        forbidden = [
            "association_members",
            "technical_responsibles",
            "traceability_events",
            "blockchain_anchors",
            "sandbox_projects",
        ]
        for name in forbidden:
            assert name not in content, (
                f"{path.name} introduz prematuramente {name!r} (reservado ao SCC)"
            )
