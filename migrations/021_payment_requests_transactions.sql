-- Migration 021: Cobranca e pagamentos (Pix/QR + conciliacao)
-- Sprint 7: dominio financeiro

BEGIN;

-- ═════════════════════════════════════════════════════════════════════
-- 1. payment_requests — cobrancas emitidas (Pix, boleto, cartao)
-- ═════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS payment_requests (
    id                 SERIAL PRIMARY KEY,
    tenant_id          INT          NOT NULL,
    clinic_id          INT          NOT NULL DEFAULT 1,
    patient_id         INT,
    prescription_id    INT,
    subscription_id    INT,

    -- Identificacao da cobranca
    external_id        VARCHAR(80)  NOT NULL UNIQUE,    -- txid do provedor / uuid interno
    description        TEXT,
    amount_cents       INTEGER      NOT NULL,
    currency           VARCHAR(3)   NOT NULL DEFAULT 'BRL',

    -- Metodo e estado
    method             VARCHAR(20)  NOT NULL DEFAULT 'pix',    -- pix, boleto, card, manual
    status             VARCHAR(20)  NOT NULL DEFAULT 'pending', -- pending, paid, expired, cancelled, refunded
    provider           VARCHAR(40)  NOT NULL DEFAULT 'manual', -- manual, mercado_pago, gerencianet, stripe

    -- Dados Pix
    pix_payload        TEXT,                                   -- EMV (BR Code copy-paste)
    pix_qr_image_url   TEXT,                                   -- QR renderizado (opcional)
    pix_key            VARCHAR(80),                            -- chave usada
    expires_at         TIMESTAMPTZ,

    -- Conciliacao
    paid_at            TIMESTAMPTZ,
    paid_amount_cents  INTEGER,

    -- Dados do provedor (imutaveis)
    provider_ref       VARCHAR(120),
    provider_metadata  JSONB        NOT NULL DEFAULT '{}'::JSONB,

    created_by         INT,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payment_requests_tenant
    ON payment_requests (tenant_id);
CREATE INDEX IF NOT EXISTS idx_payment_requests_clinic
    ON payment_requests (clinic_id);
CREATE INDEX IF NOT EXISTS idx_payment_requests_status
    ON payment_requests (status);
CREATE INDEX IF NOT EXISTS idx_payment_requests_patient
    ON payment_requests (patient_id);
CREATE INDEX IF NOT EXISTS idx_payment_requests_created
    ON payment_requests (created_at DESC);

-- ═════════════════════════════════════════════════════════════════════
-- 2. payment_transactions — movimentos financeiros (sinais de webhook)
-- ═════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS payment_transactions (
    id                 SERIAL PRIMARY KEY,
    payment_request_id INT          NOT NULL,
    tenant_id          INT          NOT NULL,
    provider           VARCHAR(40)  NOT NULL DEFAULT 'manual',
    provider_event_id  VARCHAR(120),                    -- id unico do evento no provedor

    event_type         VARCHAR(40)  NOT NULL,           -- charge.created, charge.paid, charge.failed, refund
    status             VARCHAR(20)  NOT NULL,           -- succeeded, failed, refunded
    amount_cents       INTEGER      NOT NULL,
    currency           VARCHAR(3)   NOT NULL DEFAULT 'BRL',

    payer_name         VARCHAR(200),
    payer_document     VARCHAR(40),                     -- CPF/CNPJ mascarado
    payer_account      VARCHAR(80),                     -- end-to-end Pix, se houver

    raw_payload        JSONB        NOT NULL DEFAULT '{}'::JSONB,
    received_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_payment_tx_request
        FOREIGN KEY (payment_request_id) REFERENCES payment_requests(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_payment_transactions_request
    ON payment_transactions (payment_request_id);
CREATE INDEX IF NOT EXISTS idx_payment_transactions_tenant
    ON payment_transactions (tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_transactions_provider_event
    ON payment_transactions (provider, provider_event_id)
    WHERE provider_event_id IS NOT NULL;

-- ═════════════════════════════════════════════════════════════════════
-- 3. payment_webhook_log — trilha auditavel de webhooks recebidos
-- ═════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS payment_webhook_log (
    id            SERIAL PRIMARY KEY,
    provider      VARCHAR(40)   NOT NULL,
    received_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    signature_ok  BOOLEAN       NOT NULL DEFAULT FALSE,
    status_code   INT,
    body          JSONB         NOT NULL DEFAULT '{}'::JSONB,
    headers       JSONB         NOT NULL DEFAULT '{}'::JSONB,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_payment_webhook_log_provider
    ON payment_webhook_log (provider, received_at DESC);

COMMIT;
