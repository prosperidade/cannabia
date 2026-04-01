-- Foundation da timeline longitudinal do paciente.

ALTER TABLE anamnesis_reports
    ADD COLUMN IF NOT EXISTS patient_id INT;

CREATE INDEX IF NOT EXISTS idx_anamnesis_reports_patient_id
    ON anamnesis_reports (patient_id);

INSERT INTO patients (clinic_id, name, phone)
SELECT DISTINCT
    ar.clinic_id,
    ar.patient_name,
    NULLIF(ar.phone, '')
FROM anamnesis_reports ar
WHERE NOT EXISTS (
    SELECT 1
    FROM patients p
    WHERE p.clinic_id = ar.clinic_id
      AND p.name = ar.patient_name
);

UPDATE anamnesis_reports ar
SET patient_id = (
    SELECT p.id
    FROM patients p
    WHERE p.clinic_id = ar.clinic_id
      AND p.name = ar.patient_name
    ORDER BY p.id
    LIMIT 1
)
WHERE ar.patient_id IS NULL;

CREATE TABLE IF NOT EXISTS patient_timeline_events (
    id            SERIAL PRIMARY KEY,
    clinic_id     INT           NOT NULL,
    tenant_id     INT           DEFAULT NULL,
    patient_id    INT           NOT NULL,
    event_type    VARCHAR(80)   NOT NULL,
    journey_stage VARCHAR(80)   DEFAULT NULL,
    title         VARCHAR(180)  NOT NULL,
    description   TEXT          DEFAULT NULL,
    source_type   VARCHAR(50)   DEFAULT NULL,
    source_id     INT           DEFAULT NULL,
    event_time    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata      JSONB         NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_patient_timeline_clinic_patient
    ON patient_timeline_events (clinic_id, patient_id, event_time DESC);

CREATE INDEX IF NOT EXISTS idx_patient_timeline_event_type
    ON patient_timeline_events (event_type, event_time DESC);

INSERT INTO patient_timeline_events (
    clinic_id,
    patient_id,
    event_type,
    journey_stage,
    title,
    description,
    source_type,
    source_id,
    event_time,
    metadata
)
SELECT
    ar.clinic_id,
    ar.patient_id,
    'anamnesis_completed',
    'anamnese_concluida',
    'Anamnese assistida concluída',
    'Relatório clínico gerado automaticamente a partir do fluxo de WhatsApp.',
    'anamnesis_report',
    ar.id,
    ar.created_at,
    jsonb_build_object(
        'phone', ar.phone,
        'report_model', ar.report_model,
        'rag_chunks_used', ar.rag_chunks_used
    )
FROM anamnesis_reports ar
WHERE ar.patient_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM patient_timeline_events e
      WHERE e.clinic_id = ar.clinic_id
        AND e.patient_id = ar.patient_id
        AND e.event_type = 'anamnesis_completed'
        AND e.source_type = 'anamnesis_report'
        AND e.source_id = ar.id
  );

INSERT INTO patient_timeline_events (
    clinic_id,
    patient_id,
    event_type,
    journey_stage,
    title,
    description,
    source_type,
    source_id,
    event_time,
    metadata
)
SELECT
    a.clinic_id,
    a.patient_id,
    'appointment_created',
    'agendamento_realizado',
    'Agendamento criado',
    'Consulta registrada no dashboard operacional.',
    'appointment',
    a.id,
    a.created_at,
    jsonb_build_object(
        'status', COALESCE(a.status, 'Agendada'),
        'appointment_date', to_char(a.appointment_date, 'DD/MM/YYYY HH24:MI')
    )
FROM appointments a
WHERE NOT EXISTS (
    SELECT 1
    FROM patient_timeline_events e
    WHERE e.clinic_id = a.clinic_id
      AND e.patient_id = a.patient_id
      AND e.event_type = 'appointment_created'
      AND e.source_type = 'appointment'
      AND e.source_id = a.id
);
