-- migrations/007_add_foreign_keys.sql
-- Hardening de integridade referencial nas tabelas legadas.
--
-- Estratégia:
--   1. Limpa registros órfãos ANTES de criar as constraints (DELETE seguro).
--   2. Adiciona FKs usando DO $$ ... $$ para idempotência (verifica se a constraint já existe).
--   3. Usa ON DELETE CASCADE apenas em tabelas de apoio; tabelas clínicas usam RESTRICT.
--   4. Cria índices nos campos FK para evitar degradação em JOINs e CASCADE.
--
-- IMPORTANTE: Execute em janela de manutenção se o banco tiver volume relevante.

BEGIN;

-- ═══════════════════════════════════════════════════════════════════════
-- ETAPA 1 — Limpeza de registros órfãos
-- Remove registros que referenciam clinic_id ou patient_id inexistentes.
-- Isso garante que as FKs possam ser criadas sem violação.
-- ═══════════════════════════════════════════════════════════════════════

-- patients -> clinics
DELETE FROM patients
WHERE clinic_id IS NOT NULL
  AND clinic_id NOT IN (SELECT id FROM clinics);

-- user_clinics -> users / clinics
DELETE FROM user_clinics
WHERE user_id NOT IN (SELECT id FROM users);

DELETE FROM user_clinics
WHERE clinic_id NOT IN (SELECT id FROM clinics);

-- appointments -> clinics / patients
DELETE FROM appointments
WHERE clinic_id NOT IN (SELECT id FROM clinics);

DELETE FROM appointments
WHERE patient_id NOT IN (SELECT id FROM patients);

-- incoming_messages -> clinics
DELETE FROM incoming_messages
WHERE clinic_id NOT IN (SELECT id FROM clinics);

-- message_status_updates -> clinics
DELETE FROM message_status_updates
WHERE clinic_id NOT IN (SELECT id FROM clinics);

-- ai_audit_logs -> clinics / patients
DELETE FROM ai_audit_logs
WHERE clinic_id NOT IN (SELECT id FROM clinics);

DELETE FROM ai_audit_logs
WHERE patient_id NOT IN (SELECT id FROM patients);

-- alerts -> clinics / patients (patient_id é nullable)
DELETE FROM alerts
WHERE clinic_id NOT IN (SELECT id FROM clinics);

DELETE FROM alerts
WHERE patient_id IS NOT NULL
  AND patient_id NOT IN (SELECT id FROM patients);

-- medical_history -> clinics / patients
DELETE FROM medical_history
WHERE clinic_id NOT IN (SELECT id FROM clinics);

DELETE FROM medical_history
WHERE patient_id NOT IN (SELECT id FROM patients);

-- monitoring -> clinics / patients
DELETE FROM monitoring
WHERE clinic_id NOT IN (SELECT id FROM clinics);

DELETE FROM monitoring
WHERE patient_id NOT IN (SELECT id FROM patients);

-- treatment_plans -> clinics / patients
DELETE FROM treatment_plans
WHERE clinic_id NOT IN (SELECT id FROM clinics);

DELETE FROM treatment_plans
WHERE patient_id NOT IN (SELECT id FROM patients);

-- anamnesis_reports -> clinics
DELETE FROM anamnesis_reports
WHERE clinic_id NOT IN (SELECT id FROM clinics);

-- patient_timeline_events -> clinics / patients
DELETE FROM patient_timeline_events
WHERE clinic_id NOT IN (SELECT id FROM clinics);

DELETE FROM patient_timeline_events
WHERE patient_id NOT IN (SELECT id FROM patients);

-- medical_records -> clinics / patients
DELETE FROM medical_records
WHERE clinic_id NOT IN (SELECT id FROM clinics);

DELETE FROM medical_records
WHERE patient_id NOT IN (SELECT id FROM patients);

-- medical_record_entries -> medical_records / patients
DELETE FROM medical_record_entries
WHERE medical_record_id NOT IN (SELECT id FROM medical_records);

DELETE FROM medical_record_entries
WHERE patient_id NOT IN (SELECT id FROM patients);


-- ═══════════════════════════════════════════════════════════════════════
-- ETAPA 2 — Índices nos campos FK (antes das constraints, para performance)
-- Usa IF NOT EXISTS para idempotência.
-- ═══════════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_patients_clinic_id
    ON patients (clinic_id);

CREATE INDEX IF NOT EXISTS idx_appointments_clinic_id
    ON appointments (clinic_id);

CREATE INDEX IF NOT EXISTS idx_appointments_patient_id
    ON appointments (patient_id);

CREATE INDEX IF NOT EXISTS idx_incoming_messages_clinic_id
    ON incoming_messages (clinic_id);

CREATE INDEX IF NOT EXISTS idx_message_status_updates_clinic_id
    ON message_status_updates (clinic_id);

CREATE INDEX IF NOT EXISTS idx_ai_audit_logs_clinic_id
    ON ai_audit_logs (clinic_id);

CREATE INDEX IF NOT EXISTS idx_ai_audit_logs_patient_id
    ON ai_audit_logs (patient_id);

CREATE INDEX IF NOT EXISTS idx_alerts_clinic_id
    ON alerts (clinic_id);

CREATE INDEX IF NOT EXISTS idx_alerts_patient_id
    ON alerts (patient_id);

CREATE INDEX IF NOT EXISTS idx_medical_history_clinic_id
    ON medical_history (clinic_id);

CREATE INDEX IF NOT EXISTS idx_medical_history_patient_id
    ON medical_history (patient_id);

CREATE INDEX IF NOT EXISTS idx_monitoring_clinic_id
    ON monitoring (clinic_id);

CREATE INDEX IF NOT EXISTS idx_monitoring_patient_id
    ON monitoring (patient_id);

CREATE INDEX IF NOT EXISTS idx_treatment_plans_clinic_id
    ON treatment_plans (clinic_id);

CREATE INDEX IF NOT EXISTS idx_treatment_plans_patient_id
    ON treatment_plans (patient_id);

CREATE INDEX IF NOT EXISTS idx_anamnesis_reports_clinic_id
    ON anamnesis_reports (clinic_id);

CREATE INDEX IF NOT EXISTS idx_patient_timeline_events_clinic_id
    ON patient_timeline_events (clinic_id);

CREATE INDEX IF NOT EXISTS idx_patient_timeline_events_patient_id
    ON patient_timeline_events (patient_id);

CREATE INDEX IF NOT EXISTS idx_medical_records_clinic_id
    ON medical_records (clinic_id);

CREATE INDEX IF NOT EXISTS idx_medical_record_entries_medical_record_id
    ON medical_record_entries (medical_record_id);

CREATE INDEX IF NOT EXISTS idx_medical_record_entries_patient_id
    ON medical_record_entries (patient_id);


-- ═══════════════════════════════════════════════════════════════════════
-- ETAPA 3 — Foreign Keys propriamente ditas
-- Cada bloco verifica se a constraint já existe antes de adicionar.
-- Padrão: ON DELETE RESTRICT (protege contra deleção acidental de clinics/patients).
-- ═══════════════════════════════════════════════════════════════════════

-- patients.clinic_id -> clinics.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_patients_clinic'
    ) THEN
        ALTER TABLE patients
            ADD CONSTRAINT fk_patients_clinic
            FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- user_clinics.user_id -> users.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_user_clinics_user'
    ) THEN
        ALTER TABLE user_clinics
            ADD CONSTRAINT fk_user_clinics_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- user_clinics.clinic_id -> clinics.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_user_clinics_clinic'
    ) THEN
        ALTER TABLE user_clinics
            ADD CONSTRAINT fk_user_clinics_clinic
            FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE;
    END IF;
END $$;

-- appointments.clinic_id -> clinics.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_appointments_clinic'
    ) THEN
        ALTER TABLE appointments
            ADD CONSTRAINT fk_appointments_clinic
            FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- appointments.patient_id -> patients.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_appointments_patient'
    ) THEN
        ALTER TABLE appointments
            ADD CONSTRAINT fk_appointments_patient
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- incoming_messages.clinic_id -> clinics.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_incoming_messages_clinic'
    ) THEN
        ALTER TABLE incoming_messages
            ADD CONSTRAINT fk_incoming_messages_clinic
            FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- message_status_updates.clinic_id -> clinics.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_message_status_updates_clinic'
    ) THEN
        ALTER TABLE message_status_updates
            ADD CONSTRAINT fk_message_status_updates_clinic
            FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- ai_audit_logs.clinic_id -> clinics.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_ai_audit_logs_clinic'
    ) THEN
        ALTER TABLE ai_audit_logs
            ADD CONSTRAINT fk_ai_audit_logs_clinic
            FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- ai_audit_logs.patient_id -> patients.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_ai_audit_logs_patient'
    ) THEN
        ALTER TABLE ai_audit_logs
            ADD CONSTRAINT fk_ai_audit_logs_patient
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- alerts.clinic_id -> clinics.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_alerts_clinic'
    ) THEN
        ALTER TABLE alerts
            ADD CONSTRAINT fk_alerts_clinic
            FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- alerts.patient_id -> patients.id (nullable, portanto sem ON DELETE CASCADE)
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_alerts_patient'
    ) THEN
        ALTER TABLE alerts
            ADD CONSTRAINT fk_alerts_patient
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE SET NULL;
    END IF;
END $$;

-- medical_history.clinic_id -> clinics.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_medical_history_clinic'
    ) THEN
        ALTER TABLE medical_history
            ADD CONSTRAINT fk_medical_history_clinic
            FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- medical_history.patient_id -> patients.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_medical_history_patient'
    ) THEN
        ALTER TABLE medical_history
            ADD CONSTRAINT fk_medical_history_patient
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- monitoring.clinic_id -> clinics.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_monitoring_clinic'
    ) THEN
        ALTER TABLE monitoring
            ADD CONSTRAINT fk_monitoring_clinic
            FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- monitoring.patient_id -> patients.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_monitoring_patient'
    ) THEN
        ALTER TABLE monitoring
            ADD CONSTRAINT fk_monitoring_patient
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- treatment_plans.clinic_id -> clinics.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_treatment_plans_clinic'
    ) THEN
        ALTER TABLE treatment_plans
            ADD CONSTRAINT fk_treatment_plans_clinic
            FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- treatment_plans.patient_id -> patients.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_treatment_plans_patient'
    ) THEN
        ALTER TABLE treatment_plans
            ADD CONSTRAINT fk_treatment_plans_patient
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- anamnesis_reports.clinic_id -> clinics.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_anamnesis_reports_clinic'
    ) THEN
        ALTER TABLE anamnesis_reports
            ADD CONSTRAINT fk_anamnesis_reports_clinic
            FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- patient_timeline_events.clinic_id -> clinics.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_timeline_events_clinic'
    ) THEN
        ALTER TABLE patient_timeline_events
            ADD CONSTRAINT fk_timeline_events_clinic
            FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- patient_timeline_events.patient_id -> patients.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_timeline_events_patient'
    ) THEN
        ALTER TABLE patient_timeline_events
            ADD CONSTRAINT fk_timeline_events_patient
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- medical_records.clinic_id -> clinics.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_medical_records_clinic'
    ) THEN
        ALTER TABLE medical_records
            ADD CONSTRAINT fk_medical_records_clinic
            FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- medical_records.patient_id -> patients.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_medical_records_patient'
    ) THEN
        ALTER TABLE medical_records
            ADD CONSTRAINT fk_medical_records_patient
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- medical_record_entries.medical_record_id -> medical_records.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_record_entries_record'
    ) THEN
        ALTER TABLE medical_record_entries
            ADD CONSTRAINT fk_record_entries_record
            FOREIGN KEY (medical_record_id) REFERENCES medical_records(id) ON DELETE CASCADE;
    END IF;
END $$;

-- medical_record_entries.patient_id -> patients.id
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_record_entries_patient'
    ) THEN
        ALTER TABLE medical_record_entries
            ADD CONSTRAINT fk_record_entries_patient
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE RESTRICT;
    END IF;
END $$;

COMMIT;
