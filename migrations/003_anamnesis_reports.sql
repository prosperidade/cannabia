-- migrations/003_anamnesis_reports.sql
CREATE TABLE IF NOT EXISTS anamnesis_reports (
    id                SERIAL PRIMARY KEY,
    clinic_id         INT           NOT NULL,
    patient_name      VARCHAR(200)  NOT NULL,
    phone             VARCHAR(50)   NOT NULL,
    anamnesis_data    JSONB         NOT NULL,
    clinical_analysis JSONB         NOT NULL,
    treatment_plan    JSONB         NOT NULL,
    scientific_report JSONB         NOT NULL,
    rag_chunks_used   INT           NOT NULL DEFAULT 0,
    report_model      VARCHAR(50)   NOT NULL DEFAULT 'gpt-4o-mini',
    status            VARCHAR(50)   NOT NULL DEFAULT 'pendente',
    created_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
