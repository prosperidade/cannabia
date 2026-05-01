from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "migrations" / "042_patient_app_honesty.sql").read_text(encoding="utf-8")
DOWN_SQL = (ROOT / "migrations" / "down" / "042_patient_app_honesty_down.sql").read_text(encoding="utf-8")


def test_migration_042_adds_real_appointment_fields():
    assert "ADD COLUMN IF NOT EXISTS doctor_id INT" in SQL
    assert "FOREIGN KEY (doctor_id) REFERENCES users(id)" in SQL
    assert "ADD COLUMN IF NOT EXISTS appointment_type VARCHAR(50)" in SQL
    assert "chk_appointments_type" in SQL
    assert "'teleconsulta'" in SQL
    assert "'telemonitoramento'" in SQL


def test_migration_042_adds_real_treatment_fields():
    assert "ADD COLUMN IF NOT EXISTS duration_days INT" in SQL
    assert "ADD COLUMN IF NOT EXISTS bottle_capacity_ml INT" in SQL
    assert "ADD COLUMN IF NOT EXISTS bottle_consumed_ml NUMERIC(10, 2)" in SQL


def test_migration_042_down_reverses_added_columns_and_constraints():
    assert "DROP COLUMN IF EXISTS bottle_consumed_ml" in DOWN_SQL
    assert "DROP COLUMN IF EXISTS bottle_capacity_ml" in DOWN_SQL
    assert "DROP COLUMN IF EXISTS duration_days" in DOWN_SQL
    assert "DROP CONSTRAINT IF EXISTS chk_appointments_type" in DOWN_SQL
    assert "DROP CONSTRAINT IF EXISTS fk_appointments_doctor" in DOWN_SQL
    assert "DROP COLUMN IF EXISTS doctor_id" in DOWN_SQL
