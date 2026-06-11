"""
Validacao estatica da migration 049 (TEN-2 — discriminador de tenant extensivel).

Garante por inspecao do SQL que a migration:
1. Semeia os 4 tipos futuros (pharmacy/cultivator/lawfirm/research) sem ativar.
2. Remove o CHECK literal chk_tenants_type da 024.
3. Adiciona FK referencial tenants.tenant_type -> tenant_types(slug).
4. E idempotente e tem down que restaura o estado da 024.

Validacao comportamental (UP->DOWN->UP) registrada como evidencia no PR.
"""

from __future__ import annotations

from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION = MIGRATIONS_DIR / "049_tenant_type_referential.sql"
DOWN = MIGRATIONS_DIR / "down" / "049_tenant_type_referential_down.sql"

FUTURE_TYPES = ["pharmacy", "cultivator", "lawfirm", "research"]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql() -> str:
    assert MIGRATION.exists(), f"migration ausente: {MIGRATION}"
    content = _read(MIGRATION)
    assert content.strip(), "migration 049 esta vazia"
    return content


@pytest.fixture(scope="module")
def down_sql() -> str:
    assert DOWN.exists(), f"down ausente: {DOWN}"
    return _read(DOWN)


class TestStructure:
    def test_header_references_source(self, sql: str) -> None:
        assert "TEN-2" in sql
        assert "29.1" in sql

    def test_no_manual_schema_migrations_write(self, sql: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql
        assert "UPDATE schema_migrations" not in sql


class TestSeedsFutureTypes:
    @pytest.mark.parametrize("slug", FUTURE_TYPES)
    def test_seeds_future_type(self, sql: str, slug: str) -> None:
        assert f"VALUES ('{slug}'" in sql

    def test_seeds_are_idempotent(self, sql: str) -> None:
        # cada seed usa ON CONFLICT (slug) DO NOTHING
        assert sql.count("ON CONFLICT (slug) DO NOTHING") >= len(FUTURE_TYPES)

    def test_does_not_activate_any_tenant(self, sql: str) -> None:
        # nao cria/atualiza tenants para os tipos novos
        assert "INSERT INTO tenants" not in sql
        assert "UPDATE tenants" not in sql


class TestReferentialValidation:
    def test_drops_literal_check(self, sql: str) -> None:
        assert "DROP CONSTRAINT IF EXISTS chk_tenants_type" in sql

    def test_adds_referential_fk_to_slug(self, sql: str) -> None:
        assert "ADD CONSTRAINT fk_tenants_type_slug" in sql
        assert "FOREIGN KEY (tenant_type) REFERENCES tenant_types(slug)" in sql

    def test_fk_is_idempotent(self, sql: str) -> None:
        assert "DO $$" in sql
        assert "pg_constraint" in sql

    def test_no_literal_check_re_added_in_up(self, sql: str) -> None:
        # a UP nao deve recriar o CHECK literal — a validacao agora e a FK
        assert "CHECK (tenant_type IN" not in sql


class TestDownRestores024State:
    def test_down_drops_fk(self, down_sql: str) -> None:
        assert "DROP CONSTRAINT IF EXISTS fk_tenants_type_slug" in down_sql

    def test_down_readds_literal_check(self, down_sql: str) -> None:
        assert "ADD CONSTRAINT chk_tenants_type" in down_sql
        assert "CHECK (tenant_type IN ('clinic', 'association', 'doctor'))" in down_sql

    def test_down_removes_future_types_guarded(self, down_sql: str) -> None:
        assert "DELETE FROM tenant_types" in down_sql
        # remocao guardada: so se nao referenciado por tenants
        assert "NOT IN (SELECT tenant_type_id FROM tenants" in down_sql
        assert "NOT IN (SELECT tenant_type    FROM tenants)" in down_sql or \
               "NOT IN (SELECT tenant_type FROM tenants)" in down_sql
