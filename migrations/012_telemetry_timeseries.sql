-- 012_telemetry_timeseries.sql
-- Fronteira 2: Telemetria Pós-Consulta
-- Tabelas para follow-up agendado (CRM) e dados IoT (time-series).

BEGIN;

-- ═══════════════════════════════════════════════════════════════════════════════
-- 1) Follow-ups agendados via WhatsApp (D+3, D+7, D+15)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS scheduled_followups (
    id              SERIAL PRIMARY KEY,
    clinic_id       INTEGER NOT NULL,
    patient_id      INTEGER NOT NULL,
    phone           VARCHAR(20) NOT NULL,
    report_id       INTEGER,                     -- ref: anamnesis_reports.id
    followup_type   VARCHAR(10) NOT NULL,        -- 'd3', 'd7', 'd15'
    scheduled_at    TIMESTAMPTZ NOT NULL,
    sent_at         TIMESTAMPTZ,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
                    -- pending | sent | failed | cancelled | responded
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    response_text   TEXT,                        -- resposta do paciente (se houver)
    responded_at    TIMESTAMPTZ,
    message_text    TEXT NOT NULL,               -- corpo da mensagem enviada
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_followup_patient FOREIGN KEY (patient_id)
        REFERENCES patients(id) ON DELETE CASCADE,
    CONSTRAINT chk_followup_type CHECK (followup_type IN ('d3', 'd7', 'd15')),
    CONSTRAINT chk_followup_status CHECK (
        status IN ('pending', 'sent', 'failed', 'cancelled', 'responded')
    )
);

CREATE INDEX IF NOT EXISTS idx_followup_pending
    ON scheduled_followups (status, scheduled_at)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_followup_clinic_patient
    ON scheduled_followups (clinic_id, patient_id);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 2) Telemetria IoT — Série Temporal (Sono, Frequência Cardíaca, etc.)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS iot_telemetry (
    id              BIGSERIAL PRIMARY KEY,
    clinic_id       INTEGER NOT NULL,
    patient_id      INTEGER NOT NULL,
    source          VARCHAR(30) NOT NULL,        -- 'apple_health', 'google_fit', 'manual'
    metric_type     VARCHAR(50) NOT NULL,        -- 'sleep_hours', 'heart_rate', 'spo2', 'steps', 'pain_score'
    value           NUMERIC(12,4) NOT NULL,
    unit            VARCHAR(20) NOT NULL,        -- 'hours', 'bpm', '%', 'steps', 'score_0_10'
    recorded_at     TIMESTAMPTZ NOT NULL,        -- timestamp da leitura no dispositivo
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB DEFAULT '{}',          -- dados extras do dispositivo

    CONSTRAINT fk_iot_patient FOREIGN KEY (patient_id)
        REFERENCES patients(id) ON DELETE CASCADE
);

-- Índice para consultas de série temporal (paciente + métrica + janela)
CREATE INDEX IF NOT EXISTS idx_iot_timeseries
    ON iot_telemetry (clinic_id, patient_id, metric_type, recorded_at DESC);

-- Índice para agregações por source
CREATE INDEX IF NOT EXISTS idx_iot_source
    ON iot_telemetry (source, recorded_at DESC);


-- ═══════════════════════════════════════════════════════════════════════════════
-- Tracking
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO migration_tracking (filename, description)
VALUES (
    '012_telemetry_timeseries.sql',
    'Fronteira 2: scheduled_followups (CRM D+3/D+7/D+15) e iot_telemetry (time-series)'
)
ON CONFLICT (filename) DO NOTHING;

COMMIT;
