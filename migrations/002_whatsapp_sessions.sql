-- migrations/002_whatsapp_sessions.sql
-- Tabela de estado de conversa para o fluxo de anamnese via WhatsApp
-- Execute: python -c "from src.infra.run_migrations import run_sql_file; run_sql_file('migrations/002_whatsapp_sessions.sql')"

CREATE TABLE IF NOT EXISTS whatsapp_sessions (
    id         SERIAL PRIMARY KEY,
    clinic_id  INT          NOT NULL,
    phone      VARCHAR(50)  NOT NULL,
    step       VARCHAR(50)  NOT NULL DEFAULT 'idle',
    data       JSONB        NOT NULL,
    updated_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (clinic_id, phone),
    CONSTRAINT fk_whatsapp_sessions_clinic
        FOREIGN KEY (clinic_id) REFERENCES clinics(id)
);
