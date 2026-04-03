-- migrations/011_campaign_templates.sql
-- Motor de Campanhas Ativas: templates reutilizáveis e execuções assíncronas.
--
-- Arquitetura:
--   campaign_templates  — Definição do template (corpo, variáveis, canal, tenant)
--   campaign_executions — Registro de cada disparo (status, contadores, timestamps)
--   campaign_recipients — Rastreamento por destinatário individual
--
-- Variáveis de template usam sintaxe Mustache: {{patient_name}}, {{appointment_date}}
-- Interpolação ocorre no momento do despacho em campaign_service.py.

-- ═══════════════════════════════════════════════════════════════════════════
-- Templates de Campanha
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS campaign_templates (
    id              SERIAL       PRIMARY KEY,
    tenant_id       INT          NOT NULL,
    clinic_id       INT          NOT NULL,
    name            VARCHAR(200) NOT NULL,
    description     TEXT         DEFAULT NULL,
    channel         VARCHAR(30)  NOT NULL DEFAULT 'whatsapp',
    template_body   TEXT         NOT NULL,
    variables       JSONB        NOT NULL DEFAULT '[]'::jsonb,
    status          VARCHAR(30)  NOT NULL DEFAULT 'draft',
    created_by      INT          DEFAULT NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_campaign_templates_tenant
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    CONSTRAINT fk_campaign_templates_clinic
        FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE,
    CONSTRAINT fk_campaign_templates_creator
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_campaign_channel
        CHECK (channel IN ('whatsapp', 'email', 'sms')),
    CONSTRAINT chk_campaign_template_status
        CHECK (status IN ('draft', 'active', 'archived'))
);

CREATE INDEX IF NOT EXISTS idx_campaign_templates_tenant
    ON campaign_templates (tenant_id, status);

CREATE INDEX IF NOT EXISTS idx_campaign_templates_clinic
    ON campaign_templates (clinic_id, status);


-- ═══════════════════════════════════════════════════════════════════════════
-- Execuções de Campanha
-- Um registro por disparo de campanha (pode haver múltiplos por template).
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS campaign_executions (
    id              SERIAL       PRIMARY KEY,
    template_id     INT          NOT NULL,
    tenant_id       INT          NOT NULL,
    clinic_id       INT          NOT NULL,
    target_count    INT          NOT NULL DEFAULT 0,
    sent_count      INT          NOT NULL DEFAULT 0,
    failed_count    INT          NOT NULL DEFAULT 0,
    status          VARCHAR(30)  NOT NULL DEFAULT 'queued',
    started_at      TIMESTAMP    DEFAULT NULL,
    completed_at    TIMESTAMP    DEFAULT NULL,
    error_summary   TEXT         DEFAULT NULL,
    triggered_by    INT          DEFAULT NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_campaign_executions_template
        FOREIGN KEY (template_id) REFERENCES campaign_templates(id) ON DELETE CASCADE,
    CONSTRAINT fk_campaign_executions_tenant
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    CONSTRAINT fk_campaign_executions_clinic
        FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE,
    CONSTRAINT fk_campaign_executions_user
        FOREIGN KEY (triggered_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_campaign_execution_status
        CHECK (status IN ('queued', 'sending', 'completed', 'failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_campaign_executions_template
    ON campaign_executions (template_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_campaign_executions_tenant_status
    ON campaign_executions (tenant_id, status);


-- ═══════════════════════════════════════════════════════════════════════════
-- Destinatários individuais de cada execução
-- Permite rastrear status de entrega por paciente.
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS campaign_recipients (
    id              BIGSERIAL    PRIMARY KEY,
    execution_id    INT          NOT NULL,
    patient_id      INT          NOT NULL,
    channel_address VARCHAR(120) NOT NULL,
    status          VARCHAR(30)  NOT NULL DEFAULT 'pending',
    sent_at         TIMESTAMP    DEFAULT NULL,
    error_detail    TEXT         DEFAULT NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_campaign_recipients_execution
        FOREIGN KEY (execution_id) REFERENCES campaign_executions(id) ON DELETE CASCADE,
    CONSTRAINT fk_campaign_recipients_patient
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    CONSTRAINT chk_campaign_recipient_status
        CHECK (status IN ('pending', 'sent', 'failed', 'skipped'))
);

CREATE INDEX IF NOT EXISTS idx_campaign_recipients_execution
    ON campaign_recipients (execution_id, status);

CREATE INDEX IF NOT EXISTS idx_campaign_recipients_patient
    ON campaign_recipients (patient_id);
