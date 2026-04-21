"""Static validation of migration 034 (Document Review Workflows — F4.7).

Valida por inspecao estatica do SQL que a migration:

1. Adiciona `status` + `current_stage_notes` em regulatory_reports com
   DEFAULT 'draft' e CHECK whitelist de 5 estados.
2. Cria document_review_workflows com 11 colunas, BIGSERIAL PK, 3 CHECKs
   (from_status, to_status, action) e 3 indexes.
3. Reusa prevent_update_delete() (criada em 027) via CREATE TRIGGER
   append-only + guard em pg_trigger.
4. Tem down-script reverso idempotente que preserva prevent_update_delete.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION_034 = MIGRATIONS_DIR / "034_review_workflows.sql"
MIGRATION_034_DOWN = MIGRATIONS_DIR / "down" / "034_review_workflows_down.sql"


@pytest.fixture(scope="module")
def sql_034() -> str:
    assert MIGRATION_034.exists(), MIGRATION_034
    return MIGRATION_034.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql_034_down() -> str:
    assert MIGRATION_034_DOWN.exists(), MIGRATION_034_DOWN
    return MIGRATION_034_DOWN.read_text(encoding="utf-8")


class TestAlterRegulatoryReports:
    def test_adiciona_coluna_status(self, sql_034):
        assert re.search(
            r"ADD COLUMN IF NOT EXISTS status\s+VARCHAR\(32\)\s+NOT NULL\s+DEFAULT\s+'draft'",
            sql_034, re.IGNORECASE,
        )

    def test_adiciona_coluna_current_stage_notes(self, sql_034):
        assert "ADD COLUMN IF NOT EXISTS current_stage_notes TEXT" in sql_034

    def test_check_whitelist_de_5_estados(self, sql_034):
        for state in ("draft", "rt_review", "legal_review", "approved", "rejected"):
            assert f"'{state}'" in sql_034, state
        assert "chk_reg_reports_status" in sql_034


class TestDocumentReviewWorkflows:
    def test_create_table(self, sql_034):
        assert "CREATE TABLE IF NOT EXISTS document_review_workflows" in sql_034

    def test_pk_bigserial(self, sql_034):
        assert re.search(
            r"id\s+BIGSERIAL\s+PRIMARY KEY", sql_034, re.IGNORECASE
        )

    def test_fk_report_id_e_user_id(self, sql_034):
        assert "REFERENCES regulatory_reports(id)" in sql_034
        assert "REFERENCES users(id)" in sql_034

    def test_colunas_de_assinatura(self, sql_034):
        for col in ("content_hash_at_review", "signature_hash"):
            assert f"{col}" in sql_034
            assert "CHAR(64)" in sql_034

    def test_check_actions(self, sql_034):
        for action in (
            "submit_to_rt", "rt_approve", "rt_approve_final",
            "rt_reject", "legal_approve", "legal_reject",
        ):
            assert f"'{action}'" in sql_034, action

    def test_check_from_status(self, sql_034):
        assert "chk_review_status_from" in sql_034

    def test_check_to_status(self, sql_034):
        assert "chk_review_status_to" in sql_034

    def test_tres_indexes(self, sql_034):
        for idx in (
            "idx_review_workflows_report",
            "idx_review_workflows_actor",
            "idx_review_workflows_reviewed_at",
        ):
            assert idx in sql_034, idx


class TestAppendOnlyTrigger:
    def test_guard_em_prevent_update_delete(self, sql_034):
        assert "prevent_update_delete" in sql_034
        assert "pg_proc" in sql_034
        assert "RAISE EXCEPTION" in sql_034.upper() or "raise exception" in sql_034.lower()

    def test_create_trigger_com_guard(self, sql_034):
        assert "trg_review_workflows_append_only" in sql_034
        assert "BEFORE UPDATE OR DELETE" in sql_034
        assert "pg_trigger" in sql_034


class TestDownMigration:
    def test_drop_em_ordem_inversa(self, sql_034_down):
        s = sql_034_down
        trg_pos = s.find("trg_review_workflows_append_only")
        table_pos = s.find("DROP TABLE IF EXISTS document_review_workflows")
        col_pos = s.find("DROP COLUMN IF EXISTS status")
        assert -1 < trg_pos < table_pos < col_pos

    def test_nao_dropa_prevent_update_delete(self, sql_034_down):
        assert "DROP FUNCTION" not in sql_034_down.upper() or "prevent_update_delete" not in sql_034_down.replace("DROP FUNCTION", "")

    def test_drop_constraint_e_duas_colunas(self, sql_034_down):
        assert "DROP CONSTRAINT IF EXISTS chk_reg_reports_status" in sql_034_down
        assert "DROP COLUMN IF EXISTS current_stage_notes" in sql_034_down
        assert "DROP COLUMN IF EXISTS status" in sql_034_down

    def test_down_e_idempotente(self, sql_034_down):
        # Cada statement DDL completo (terminado em ;) tem IF EXISTS.
        # Statements podem ser multi-linha (ex.: ALTER TABLE ... DROP ...);
        # por isso agrupamos por ';' e ignoramos comentarios de linha.
        clean = "\n".join(
            line for line in sql_034_down.splitlines()
            if not line.strip().startswith("--")
        )
        for stmt in [s.strip() for s in clean.split(";") if s.strip()]:
            head = stmt.split()[0].upper()
            if head in {"DROP", "ALTER"}:
                assert "IF EXISTS" in stmt.upper(), stmt


class TestMigrationHasModuleDocstring:
    def test_cabecalho_menciona_fase_e_doc(self, sql_034):
        s = sql_034[:1500]
        assert "F4.7" in s
        assert "doc 27" in s
        assert "aprovacao bilateral" in s
