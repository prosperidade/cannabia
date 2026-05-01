-- Rollback da migration 042.
BEGIN;

ALTER TABLE treatment_plans DROP COLUMN IF EXISTS bottle_consumed_ml;
ALTER TABLE treatment_plans DROP COLUMN IF EXISTS bottle_capacity_ml;
ALTER TABLE treatment_plans DROP COLUMN IF EXISTS duration_days;

ALTER TABLE appointments DROP CONSTRAINT IF EXISTS chk_appointments_type;
ALTER TABLE appointments DROP COLUMN IF EXISTS appointment_type;

ALTER TABLE appointments DROP CONSTRAINT IF EXISTS fk_appointments_doctor;
DROP INDEX IF EXISTS idx_appointments_doctor_id;
ALTER TABLE appointments DROP COLUMN IF EXISTS doctor_id;

COMMIT;
