"""
Validacao estatica da migration 056 (Onda 2 / Track REG · REG-3 — condição
grave/debilitante / cuidados paliativos na prescrição).

Garante por inspecao do SQL que a migration:
1. Adiciona prescriptions.regulatory_condition (default 'nenhuma').
2. Adiciona prescriptions.clinical_justification (TEXT).
3. Tem CHECK de dominio com os 3 valores do enum RegulatoryCondition.
4. E aditiva e idempotente (IF NOT EXISTS + guarda da constraint via pg_constraint).
5. Tem down que remove a constraint + as 2 colunas.

Validacao comportamental (UP->DOWN->UP) registrada como evidencia no PR.
"""
from __future__ import annotations

from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION = MIGRATIONS_DIR / "056_regulatory_condition.sql"
DOWN = MIGRATIONS_DIR / "down" / "056_regulatory_condition_down.sql"


def _up() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _down() -> str:
    return DOWN.read_text(encoding="utf-8")


def test_arquivos_existem():
    assert MIGRATION.exists()
    assert DOWN.exists()


def test_up_adiciona_as_duas_colunas():
    up = _up().lower()
    assert "add column if not exists regulatory_condition" in up
    assert "add column if not exists clinical_justification" in up
    assert "default 'nenhuma'" in up


def test_up_tem_check_dos_tres_valores():
    up = _up().lower()
    assert "check" in up
    for valor in ("nenhuma", "grave_debilitante", "paliativa"):
        assert valor in up


def test_up_e_idempotente():
    up = _up()
    assert "IF NOT EXISTS" in up          # colunas
    assert "pg_constraint" in up          # guarda da constraint


def test_down_remove_constraint_e_colunas():
    down = _down().lower()
    assert "drop constraint if exists ck_prescriptions_regulatory_condition" in down
    assert "drop column if exists clinical_justification" in down
    assert "drop column if exists regulatory_condition" in down
