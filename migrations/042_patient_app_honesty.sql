-- Migration 042: Schema honesty para o app do paciente.
--
-- Hoje o backend retorna placeholders fingindo dado real:
--   - appointments.doctor   = "A confirmar"
--   - appointments.modality = "presencial"
--   - treatment.bottle_remaining_pct = 68 hardcoded
--   - patient.treatment_total_days   = null (sem coluna no schema)
--
-- Esta migration adiciona as colunas que faltam, para que o backend possa
-- retornar valor real quando preenchido e null quando vazio. O frontend
-- ja trata null escondendo o pedaco correspondente.
--
--   appointments.doctor_id INT FK users(id)
--   appointments.appointment_type VARCHAR(50)
--                  CHECK in (presencial|teleconsulta|telemonitoramento)
--   treatment_plans.duration_days INT
--   treatment_plans.bottle_capacity_ml INT
--   treatment_plans.bottle_consumed_ml NUMERIC(10,2)
--
-- bottle_remaining_pct e calculado em runtime a partir de
-- (capacity - consumed) / capacity * 100; quando faltar dado, null.
--
-- Idempotente.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. appointments
-- ---------------------------------------------------------------------------

ALTER TABLE appointments
    ADD COLUMN IF NOT EXISTS doctor_id INT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_appointments_doctor'
          AND table_name = 'appointments'
    ) THEN
        ALTER TABLE appointments
            ADD CONSTRAINT fk_appointments_doctor
            FOREIGN KEY (doctor_id) REFERENCES users(id);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_appointments_doctor_id
    ON appointments (doctor_id);

ALTER TABLE appointments
    ADD COLUMN IF NOT EXISTS appointment_type VARCHAR(50);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'chk_appointments_type'
          AND table_name = 'appointments'
    ) THEN
        ALTER TABLE appointments
            ADD CONSTRAINT chk_appointments_type
            CHECK (
                appointment_type IS NULL
                OR appointment_type IN (
                    'presencial', 'teleconsulta', 'telemonitoramento'
                )
            );
    END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- 2. treatment_plans
-- ---------------------------------------------------------------------------

ALTER TABLE treatment_plans
    ADD COLUMN IF NOT EXISTS duration_days INT;

ALTER TABLE treatment_plans
    ADD COLUMN IF NOT EXISTS bottle_capacity_ml INT;

ALTER TABLE treatment_plans
    ADD COLUMN IF NOT EXISTS bottle_consumed_ml NUMERIC(10, 2);

COMMIT;
