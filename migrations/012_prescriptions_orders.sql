-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration 012: Prescriptions & B2B Orders (Fronteira 3)
-- Tabelas para persistência de prescrições de dosagem e pedidos B2B marketplace.
-- ═══════════════════════════════════════════════════════════════════════════════

-- ── Prescrições de Dosagem ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS prescriptions (
    id              SERIAL PRIMARY KEY,
    clinic_id       INTEGER NOT NULL,
    patient_id      INTEGER NOT NULL,
    doctor_user_id  INTEGER NOT NULL,
    doctor_name     VARCHAR(255) NOT NULL,
    doctor_crm      VARCHAR(20) NOT NULL,

    -- Recomendação de dosagem
    cannabinoid_ratio       VARCHAR(50) NOT NULL,
    spectrum                VARCHAR(30) NOT NULL,
    administration_route    VARCHAR(30) NOT NULL,
    concentration_mg_ml     NUMERIC(8,2) NOT NULL,
    max_daily_mg            NUMERIC(8,2) NOT NULL,

    -- Protocolo detalhado (JSONB)
    titration_protocol      JSONB NOT NULL DEFAULT '[]',
    clinical_rationale      TEXT NOT NULL,
    contraindications       JSONB NOT NULL DEFAULT '[]',
    drug_interactions       JSONB NOT NULL DEFAULT '[]',
    monitoring_checkpoints  JSONB NOT NULL DEFAULT '[]',
    confidence_score        NUMERIC(3,2) NOT NULL DEFAULT 0.0,
    evidence_sources        JSONB NOT NULL DEFAULT '[]',
    safety_limits           JSONB NOT NULL DEFAULT '{}',

    -- Metadados
    custom_notes    TEXT,
    validity_days   INTEGER NOT NULL DEFAULT 180,
    status          VARCHAR(20) NOT NULL DEFAULT 'active',

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_prescriptions_clinic_id ON prescriptions(clinic_id);
CREATE INDEX IF NOT EXISTS idx_prescriptions_patient_id ON prescriptions(clinic_id, patient_id);
CREATE INDEX IF NOT EXISTS idx_prescriptions_doctor ON prescriptions(clinic_id, doctor_user_id);
CREATE INDEX IF NOT EXISTS idx_prescriptions_status ON prescriptions(clinic_id, status);
CREATE INDEX IF NOT EXISTS idx_prescriptions_created ON prescriptions(clinic_id, created_at DESC);


-- ── Pedidos B2B para Associações Parceiras ───────────────────────────────────

CREATE TABLE IF NOT EXISTS b2b_orders (
    id                      SERIAL PRIMARY KEY,
    order_ref               VARCHAR(50) NOT NULL UNIQUE,
    prescription_id         INTEGER NOT NULL REFERENCES prescriptions(id),
    clinic_id               INTEGER NOT NULL,
    patient_id              INTEGER NOT NULL,

    -- Dados do pedido
    patient_name            VARCHAR(255) NOT NULL DEFAULT '',
    doctor_crm              VARCHAR(20) NOT NULL,
    products                JSONB NOT NULL DEFAULT '[]',
    dosage_summary          TEXT NOT NULL,
    cannabinoid_ratio       VARCHAR(50) NOT NULL,
    administration_route    VARCHAR(30) NOT NULL,
    total_daily_mg          NUMERIC(8,2) NOT NULL DEFAULT 0.0,
    treatment_duration_days INTEGER NOT NULL DEFAULT 90,

    -- Entrega
    shipping_address        JSONB,
    notes                   TEXT,

    -- Status tracking
    status                  VARCHAR(20) NOT NULL DEFAULT 'pending',
    sent_at                 TIMESTAMPTZ,
    confirmed_at            TIMESTAMPTZ,
    fulfilled_at            TIMESTAMPTZ,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_b2b_orders_clinic_id ON b2b_orders(clinic_id);
CREATE INDEX IF NOT EXISTS idx_b2b_orders_prescription ON b2b_orders(prescription_id);
CREATE INDEX IF NOT EXISTS idx_b2b_orders_status ON b2b_orders(clinic_id, status);
CREATE INDEX IF NOT EXISTS idx_b2b_orders_created ON b2b_orders(clinic_id, created_at DESC);


-- ── Registro da migration ────────────────────────────────────────────────────

INSERT INTO schema_migrations (version, filename, applied_at, checksum)
VALUES ('012', '012_prescriptions_orders.sql', NOW(), '')
ON CONFLICT DO NOTHING;
