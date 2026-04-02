-- Foundation mínima de prontuário longitudinal.

CREATE TABLE IF NOT EXISTS medical_records (
    id                SERIAL PRIMARY KEY,
    clinic_id         INT           NOT NULL,
    tenant_id         INT           DEFAULT NULL,
    patient_id        INT           NOT NULL,
    primary_doctor_id INT           DEFAULT NULL,
    status            VARCHAR(50)   NOT NULL DEFAULT 'ativo',
    opened_at         TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_entry_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_medical_records_clinic_patient
    ON medical_records (clinic_id, patient_id);

CREATE INDEX IF NOT EXISTS idx_medical_records_patient
    ON medical_records (patient_id, clinic_id);

CREATE TABLE IF NOT EXISTS medical_record_entries (
    id                  SERIAL PRIMARY KEY,
    clinic_id           INT           NOT NULL,
    tenant_id           INT           DEFAULT NULL,
    medical_record_id   INT           NOT NULL,
    patient_id          INT           NOT NULL,
    author_user_id      INT           DEFAULT NULL,
    author_name         VARCHAR(100)  DEFAULT NULL,
    entry_type          VARCHAR(50)   NOT NULL,
    source_report_id    INT           DEFAULT NULL,
    title               VARCHAR(180)  NOT NULL,
    status              VARCHAR(50)   NOT NULL DEFAULT 'rascunho',
    medical_observations TEXT         DEFAULT NULL,
    clinical_assessment TEXT          DEFAULT NULL,
    conduct             TEXT          DEFAULT NULL,
    requested_exams     JSONB         NOT NULL DEFAULT '[]'::jsonb,
    follow_up_plan      TEXT          DEFAULT NULL,
    metadata            JSONB         NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_medical_record_entries_report_type
    ON medical_record_entries (clinic_id, patient_id, source_report_id, entry_type);

CREATE INDEX IF NOT EXISTS idx_medical_record_entries_record
    ON medical_record_entries (medical_record_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_medical_record_entries_patient
    ON medical_record_entries (patient_id, clinic_id, created_at DESC);

INSERT INTO medical_records (
    clinic_id,
    tenant_id,
    patient_id,
    status,
    opened_at,
    last_entry_at
)
SELECT
    ar.clinic_id,
    c.tenant_id,
    ar.patient_id,
    'ativo',
    MIN(ar.created_at),
    MAX(ar.created_at)
FROM anamnesis_reports ar
LEFT JOIN clinics c ON c.id = ar.clinic_id
WHERE ar.patient_id IS NOT NULL
GROUP BY ar.clinic_id, c.tenant_id, ar.patient_id
ON CONFLICT (clinic_id, patient_id) DO NOTHING;

INSERT INTO medical_record_entries (
    clinic_id,
    tenant_id,
    medical_record_id,
    patient_id,
    author_name,
    entry_type,
    source_report_id,
    title,
    status,
    medical_observations,
    clinical_assessment,
    conduct,
    requested_exams,
    follow_up_plan,
    metadata,
    created_at,
    updated_at
)
SELECT
    ar.clinic_id,
    mr.tenant_id,
    mr.id,
    ar.patient_id,
    'sistema',
    'anamnesis_snapshot',
    ar.id,
    'Anamnese assistida importada',
    CASE WHEN ar.status = 'revisado' THEN 'importado_revisado' ELSE 'importado' END,
    COALESCE(ar.anamnesis_data->>'medical_history', ''),
    CONCAT(
        'Risco: ',
        COALESCE(ar.clinical_analysis->>'risk_level', 'N/A'),
        CASE
            WHEN jsonb_array_length(COALESCE(ar.clinical_analysis->'probable_conditions', '[]'::jsonb)) > 0
            THEN CONCAT(' | Condições prováveis: ', array_to_string(ARRAY(
                SELECT jsonb_array_elements_text(ar.clinical_analysis->'probable_conditions')
            ), ', '))
            ELSE ''
        END
    ),
    COALESCE(ar.treatment_plan->>'suggested_dosage', ''),
    COALESCE(ar.clinical_analysis->'recommended_exams', '[]'::jsonb),
    COALESCE(ar.treatment_plan->>'monitoring_plan', ''),
    jsonb_build_object(
        'source', 'anamnesis_report',
        'report_model', ar.report_model,
        'rag_chunks_used', ar.rag_chunks_used,
        'phone', ar.phone
    ),
    ar.created_at,
    ar.updated_at
FROM anamnesis_reports ar
JOIN medical_records mr
  ON mr.clinic_id = ar.clinic_id
 AND mr.patient_id = ar.patient_id
WHERE ar.patient_id IS NOT NULL
ON CONFLICT (clinic_id, patient_id, source_report_id, entry_type) DO NOTHING;

UPDATE medical_records mr
SET last_entry_at = entry_data.max_created_at,
    updated_at = CURRENT_TIMESTAMP
FROM (
    SELECT medical_record_id, MAX(created_at) AS max_created_at
    FROM medical_record_entries
    GROUP BY medical_record_id
) AS entry_data
WHERE mr.id = entry_data.medical_record_id;
