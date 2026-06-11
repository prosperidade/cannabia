"""
Validacao estatica da migration 048 (TEN-1 — FKs do eixo tenant).

Garante por inspecao do SQL que a migration:
1. Limpa orfaos ANTES de criar as constraints.
2. Adiciona as 3 FKs do eixo tenant com os alvos e ON DELETE corretos.
3. Usa DO $$ + pg_constraint (idempotente).
4. Tem down script que dropa exatamente as 3 constraints.

Validacao comportamental (UP->DOWN->UP contra Postgres real) e registrada
como evidencia no PR do Track A.
"""

from __future__ import annotations

from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION = MIGRATIONS_DIR / "048_tenant_axis_foreign_keys.sql"
DOWN = MIGRATIONS_DIR / "down" / "048_tenant_axis_foreign_keys_down.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql() -> str:
    assert MIGRATION.exists(), f"migration ausente: {MIGRATION}"
    content = _read(MIGRATION)
    assert content.strip(), "migration 048 esta vazia"
    return content


@pytest.fixture(scope="module")
def down_sql() -> str:
    assert DOWN.exists(), f"down ausente: {DOWN}"
    return _read(DOWN)


class TestStructure:
    def test_header_references_source(self, sql: str) -> None:
        assert "TEN-1" in sql
        assert "29.1" in sql

    def test_no_manual_schema_migrations_write(self, sql: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql
        assert "UPDATE schema_migrations" not in sql


class TestOrphanCleanupBeforeConstraints:
    def test_clinics_orphans_set_null(self, sql: str) -> None:
        assert "UPDATE clinics" in sql
        assert "SET tenant_id = NULL" in sql
        assert "tenant_id NOT IN (SELECT id FROM tenants)" in sql

    def test_user_tenant_roles_orphans_deleted(self, sql: str) -> None:
        assert "DELETE FROM user_tenant_roles" in sql
        assert "user_id NOT IN (SELECT id FROM users)" in sql
        assert "tenant_id NOT IN (SELECT id FROM tenants)" in sql

    def test_cleanup_precedes_constraints(self, sql: str) -> None:
        cleanup_pos = sql.find("SET tenant_id = NULL")
        first_fk_pos = sql.find("ADD CONSTRAINT fk_clinics_tenant_id")
        assert 0 < cleanup_pos < first_fk_pos, (
            "limpeza de orfaos deve vir ANTES de adicionar as FKs"
        )


class TestForeignKeys:
    def test_clinics_tenant_fk_set_null(self, sql: str) -> None:
        assert "ADD CONSTRAINT fk_clinics_tenant_id" in sql
        assert "FOREIGN KEY (tenant_id) REFERENCES tenants(id)" in sql
        # ponte nullable -> SET NULL preserva a clinica
        clinics_block = sql[sql.find("fk_clinics_tenant_id"):]
        assert "ON DELETE SET NULL" in clinics_block[:200]

    def test_user_tenant_roles_user_fk_cascade(self, sql: str) -> None:
        assert "ADD CONSTRAINT fk_user_tenant_roles_user" in sql
        assert "FOREIGN KEY (user_id) REFERENCES users(id)" in sql
        block = sql[sql.find("ADD CONSTRAINT fk_user_tenant_roles_user"):]
        assert "ON DELETE CASCADE" in block[:220]

    def test_user_tenant_roles_tenant_fk_cascade(self, sql: str) -> None:
        assert "ADD CONSTRAINT fk_user_tenant_roles_tenant" in sql
        block = sql[sql.find("ADD CONSTRAINT fk_user_tenant_roles_tenant"):]
        assert "FOREIGN KEY (tenant_id) REFERENCES tenants(id)" in block[:220]
        assert "ON DELETE CASCADE" in block[:260]

    def test_three_fks_total(self, sql: str) -> None:
        assert sql.count("ADD CONSTRAINT fk_") == 3


class TestIdempotency:
    def test_constraints_guarded_by_pg_constraint(self, sql: str) -> None:
        assert sql.count("DO $$") >= 3
        assert sql.count("pg_constraint") >= 3

    def test_no_drop_table_or_column(self, sql: str) -> None:
        assert "DROP TABLE" not in sql
        assert "DROP COLUMN" not in sql


class TestDownScript:
    def test_down_drops_three_constraints(self, down_sql: str) -> None:
        assert "DROP CONSTRAINT IF EXISTS fk_clinics_tenant_id" in down_sql
        assert "DROP CONSTRAINT IF EXISTS fk_user_tenant_roles_user" in down_sql
        assert "DROP CONSTRAINT IF EXISTS fk_user_tenant_roles_tenant" in down_sql

    def test_down_is_non_destructive_to_data(self, down_sql: str) -> None:
        # Ignora linhas de comentario (o cabecalho cita o procedimento manual
        # "DELETE FROM schema_migrations" do README de rollback).
        code = "\n".join(
            line for line in down_sql.splitlines()
            if not line.lstrip().startswith("--")
        )
        assert "DROP TABLE" not in code
        assert "DELETE FROM" not in code
