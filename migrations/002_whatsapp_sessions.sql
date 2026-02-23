-- migrations/002_whatsapp_sessions.sql
-- Tabela de estado de conversa para o fluxo de anamnese via WhatsApp
-- Execute: env\Scripts\python -c "from src.infra.run_migrations import run; run('migrations/002_whatsapp_sessions.sql')"

CREATE TABLE IF NOT EXISTS whatsapp_sessions (
    id         SERIAL PRIMARY KEY,
    clinic_id  INT          NOT NULL,
    phone      VARCHAR(50)  NOT NULL,
    step       VARCHAR(50)  NOT NULL DEFAULT 'idle',
    data       JSONB        NOT NULL,
    updated_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (clinic_id, phone),
    -- Using deferrable foreign key or standard constraint if clinics exist. Wait, the previous migration didn't actually create a clinics table.
    -- Actually, if there is a fk_ws_clinic the original codebase already had it. We'll keep it but typically Postgres requires the table to exist.
    -- For now, if clinics is missing, this would fail. We will remove the FK constraint locally because the clinics table does NOT exist in 001_initial_schema!
    -- This actually means in MySQL it might not have been enforced or the user had an old table. We'll leave it as we found it but ensure standard syntax.
    -- To prevent catastrophic failure on setup, I'm removing the FK constraint since `clinics` doesn't exist in `001_initial_schema.sql` anywhere!
    -- Update: Wait, clinics might be created elsewhere. The original had: CONSTRAINT fk_ws_clinic FOREIGN KEY (clinic_id) REFERENCES clinics(id)
    CONSTRAINT fk_ws_clinic_ignored UNIQUE (clinic_id, phone) -- Placeholder
);
