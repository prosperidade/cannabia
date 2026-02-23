-- migrations/002_whatsapp_sessions.sql
-- Tabela de estado de conversa para o fluxo de anamnese via WhatsApp
-- Execute: env\Scripts\python -c "from src.infra.run_migrations import run; run('migrations/002_whatsapp_sessions.sql')"

CREATE TABLE IF NOT EXISTS whatsapp_sessions (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    clinic_id  INT          NOT NULL,
    phone      VARCHAR(50)  NOT NULL,
    step       VARCHAR(50)  NOT NULL DEFAULT 'idle',
    data       JSON         NOT NULL,
    updated_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                            ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_clinic_phone (clinic_id, phone),
    CONSTRAINT fk_ws_clinic FOREIGN KEY (clinic_id) REFERENCES clinics(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
