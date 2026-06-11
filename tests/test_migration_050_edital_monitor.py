"""
Validacao estatica da migration 050 (SCC-2 / A6 — monitor do edital do sandbox).

Garante por inspecao do SQL que a migration:
1. Semeia 2 monitores (DOU + Anvisa) para o edital da RDC 1.014.
2. Reusa a tabela knowledge_monitors (017) — nao cria tabela nova.
3. E idempotente (INSERT guardado por NOT EXISTS no name).
4. Usa linguagem de vigilancia COMERCIAL (nao de obrigacao regulatoria propria).
5. Tem down que remove exatamente os 2 seeds.

Validacao comportamental (UP->DOWN->UP) registrada como evidencia no PR.
"""

from __future__ import annotations

from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION = MIGRATIONS_DIR / "050_seed_edital_monitor.sql"
DOWN = MIGRATIONS_DIR / "down" / "050_seed_edital_monitor_down.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql() -> str:
    assert MIGRATION.exists(), f"migration ausente: {MIGRATION}"
    content = _read(MIGRATION)
    assert content.strip(), "migration 050 esta vazia"
    return content


@pytest.fixture(scope="module")
def down_sql() -> str:
    assert DOWN.exists(), f"down ausente: {DOWN}"
    return _read(DOWN)


class TestStructure:
    def test_header_references_source(self, sql: str) -> None:
        assert "SCC-2" in sql or "A6" in sql
        assert "1.014" in sql

    def test_reuses_knowledge_monitors_table(self, sql: str) -> None:
        assert "INSERT INTO knowledge_monitors" in sql
        # nao cria tabela nova — reusa a 017
        assert "CREATE TABLE" not in sql

    def test_no_manual_schema_migrations_write(self, sql: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql
        assert "UPDATE schema_migrations" not in sql


class TestSeedsTwoMonitors:
    def test_two_inserts(self, sql: str) -> None:
        assert sql.count("INSERT INTO knowledge_monitors") == 2

    def test_watches_dou(self, sql: str) -> None:
        assert "'dou'" in sql
        assert "in.gov.br" in sql

    def test_watches_anvisa(self, sql: str) -> None:
        assert "'anvisa'" in sql
        assert "gov.br/anvisa" in sql

    def test_targets_the_edital(self, sql: str) -> None:
        assert "edital" in sql.lower()
        assert "sandbox" in sql.lower()

    def test_idempotent_guard(self, sql: str) -> None:
        # cada INSERT guardado por NOT EXISTS no name
        assert sql.count("WHERE NOT EXISTS") == 2


class TestCommercialFraming:
    def test_language_is_commercial_not_obligation(self, sql: str) -> None:
        # framing fixado: vigilancia comercial, nunca obrigacao/prazo proprio
        assert "comercial" in sql.lower()
        # nao deve sugerir que a CannabIA submete/concorre
        lowered = sql.lower()
        assert "prazo" not in lowered or "sem data" in lowered


class TestDownScript:
    def test_down_removes_both_seeds(self, down_sql: str) -> None:
        assert "DELETE FROM knowledge_monitors" in down_sql
        assert down_sql.count("EDITAL Sandbox RDC 1.014") == 2

    def test_down_is_scoped(self, down_sql: str) -> None:
        # nao apaga a tabela nem outros monitores
        assert "DROP TABLE" not in down_sql
        assert "WHERE name IN" in down_sql
