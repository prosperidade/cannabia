-- Migration 018: Triage links — persistencia, uso unico e vinculo com agendamento
-- Sprint 1: fechar o fluxo agendamento -> link triagem -> atendimento

-- =====================================================
-- 1. Tabela de links de triagem emitidos
-- =====================================================
CREATE TABLE IF NOT EXISTS triage_links (
    id              SERIAL PRIMARY KEY,
    clinic_id       INT          NOT NULL,
    appointment_id  INT,
    patient_id      INT,
    patient_name    VARCHAR(200),
    patient_phone   VARCHAR(30),
    token_hash      VARCHAR(128) NOT NULL,
    issued_by       INT,
    issued_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ  NOT NULL,
    used_at         TIMESTAMPTZ,
    used_by_ip      VARCHAR(45),
    report_id       INT,
    status          VARCHAR(20)  NOT NULL DEFAULT 'active',

    CONSTRAINT fk_triage_links_clinic
        FOREIGN KEY (clinic_id) REFERENCES clinics(id),
    CONSTRAINT fk_triage_links_appointment
        FOREIGN KEY (appointment_id) REFERENCES appointments(id),
    CONSTRAINT fk_triage_links_patient
        FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_triage_links_issued_by
        FOREIGN KEY (issued_by) REFERENCES users(id),
    CONSTRAINT fk_triage_links_report
        FOREIGN KEY (report_id) REFERENCES anamnesis_reports(id)
);

CREATE INDEX IF NOT EXISTS idx_triage_links_token_hash
    ON triage_links (token_hash);

CREATE INDEX IF NOT EXISTS idx_triage_links_clinic_status
    ON triage_links (clinic_id, status);

CREATE INDEX IF NOT EXISTS idx_triage_links_appointment
    ON triage_links (appointment_id)
    WHERE appointment_id IS NOT NULL;

-- =====================================================
-- 2. Vincular anamnesis_reports ao agendamento e ao link
-- =====================================================
ALTER TABLE anamnesis_reports
    ADD COLUMN IF NOT EXISTS appointment_id INT,
    ADD COLUMN IF NOT EXISTS triage_link_id INT;

-- Foreign keys condicionais (sem quebrar se ja existirem)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_reports_appointment'
          AND table_name = 'anamnesis_reports'
    ) THEN
        ALTER TABLE anamnesis_reports
            ADD CONSTRAINT fk_reports_appointment
            FOREIGN KEY (appointment_id) REFERENCES appointments(id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_reports_triage_link'
          AND table_name = 'anamnesis_reports'
    ) THEN
        ALTER TABLE anamnesis_reports
            ADD CONSTRAINT fk_reports_triage_link
            FOREIGN KEY (triage_link_id) REFERENCES triage_links(id);
    END IF;
END
$$;

-- =====================================================
-- 3. Adicionar appointment_id na tabela appointments
--    para rastrear status do link emitido
-- =====================================================
ALTER TABLE appointments
    ADD COLUMN IF NOT EXISTS triage_link_id INT,
    ADD COLUMN IF NOT EXISTS notes TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_appointments_triage_link'
          AND table_name = 'appointments'
    ) THEN
        ALTER TABLE appointments
            ADD CONSTRAINT fk_appointments_triage_link
            FOREIGN KEY (triage_link_id) REFERENCES triage_links(id);
    END IF;
END
$$;
