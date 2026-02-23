-- migrations/003_anamnesis_reports.sql
CREATE TABLE IF NOT EXISTS anamnesis_reports (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    clinic_id         INT           NOT NULL,
    patient_name      VARCHAR(200)  NOT NULL,
    phone             VARCHAR(50)   NOT NULL,
    anamnesis_data    JSON          NOT NULL,
    clinical_analysis JSON          NOT NULL,
    treatment_plan    JSON          NOT NULL,
    scientific_report JSON          NOT NULL,
    rag_chunks_used   INT           NOT NULL DEFAULT 0,
    report_model      VARCHAR(50)   NOT NULL DEFAULT 'gpt-4o-mini',
    status            ENUM('pendente','revisado') NOT NULL DEFAULT 'pendente',
    created_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_ar_clinic FOREIGN KEY (clinic_id) REFERENCES clinics(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
