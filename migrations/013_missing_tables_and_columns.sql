-- Migration 013: Tabelas e colunas faltantes para o frontend completo
-- Resolve gaps entre o que os endpoints consultam e o que existe no schema

-- ====================================================================
-- 1. patients: adicionar user_id e status
-- ====================================================================
ALTER TABLE patients ADD COLUMN IF NOT EXISTS user_id INT;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'ativo';
CREATE INDEX IF NOT EXISTS idx_patients_user_id ON patients (user_id);

-- ====================================================================
-- 2. treatment_plans: expandir com colunas clinicas
-- ====================================================================
ALTER TABLE treatment_plans ADD COLUMN IF NOT EXISTS plan_name VARCHAR(255);
ALTER TABLE treatment_plans ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'ativo';
ALTER TABLE treatment_plans ADD COLUMN IF NOT EXISTS cbd_thc_ratio VARCHAR(50);
ALTER TABLE treatment_plans ADD COLUMN IF NOT EXISTS dosage VARCHAR(255);
ALTER TABLE treatment_plans ADD COLUMN IF NOT EXISTS frequency VARCHAR(100);
ALTER TABLE treatment_plans ADD COLUMN IF NOT EXISTS route VARCHAR(50) DEFAULT 'sublingual';
ALTER TABLE treatment_plans ADD COLUMN IF NOT EXISTS precautions JSONB DEFAULT '[]'::jsonb;
ALTER TABLE treatment_plans ADD COLUMN IF NOT EXISTS schedule JSONB DEFAULT '[]'::jsonb;
ALTER TABLE treatment_plans ADD COLUMN IF NOT EXISTS adjustment_history JSONB DEFAULT '[]'::jsonb;
ALTER TABLE treatment_plans ADD COLUMN IF NOT EXISTS next_return_date TIMESTAMPTZ;
ALTER TABLE treatment_plans ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- ====================================================================
-- 3. symptom_diary: diario de sintomas do paciente
-- ====================================================================
CREATE TABLE IF NOT EXISTS symptom_diary (
    id              SERIAL PRIMARY KEY,
    clinic_id       INT NOT NULL DEFAULT 1,
    patient_id      INT,
    user_id         INT,
    overall_score   INT NOT NULL,
    pain_level      INT,
    sleep_quality   INT,
    mood            VARCHAR(50),
    side_effects    JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes           TEXT DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_symptom_diary_patient ON symptom_diary (patient_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_symptom_diary_user ON symptom_diary (user_id, created_at DESC);

-- ====================================================================
-- 4. stock_inventory: estoque de produtos canabicos
-- ====================================================================
CREATE TABLE IF NOT EXISTS stock_inventory (
    id              SERIAL PRIMARY KEY,
    clinic_id       INT NOT NULL DEFAULT 1,
    product_name    VARCHAR(255) NOT NULL,
    batch_number    VARCHAR(100),
    quantity        INT NOT NULL DEFAULT 0,
    unit            VARCHAR(50) DEFAULT 'frascos',
    expiry_date     DATE,
    status          VARCHAR(50) DEFAULT 'disponivel',
    supplier        VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stock_inventory_clinic ON stock_inventory (clinic_id);

-- ====================================================================
-- 5. stock_dispensations: dispensacao de estoque ao paciente
-- ====================================================================
CREATE TABLE IF NOT EXISTS stock_dispensations (
    id              SERIAL PRIMARY KEY,
    clinic_id       INT NOT NULL DEFAULT 1,
    stock_item_id   INT NOT NULL REFERENCES stock_inventory(id),
    patient_id      INT NOT NULL REFERENCES patients(id),
    quantity        INT NOT NULL,
    dispensed_by    INT,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stock_dispensations_clinic ON stock_dispensations (clinic_id);

-- ====================================================================
-- 6. billing: faturamento clinico simples
-- ====================================================================
CREATE TABLE IF NOT EXISTS billing (
    id              SERIAL PRIMARY KEY,
    clinic_id       INT NOT NULL DEFAULT 1,
    patient_id      INT,
    description     TEXT,
    amount          NUMERIC(10,2) NOT NULL DEFAULT 0,
    status          VARCHAR(50) DEFAULT 'pendente',
    due_date        DATE,
    paid_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_billing_clinic ON billing (clinic_id);
CREATE INDEX IF NOT EXISTS idx_billing_status ON billing (status);

-- ====================================================================
-- 7. View clinic_members (alias para user_clinics)
-- Resolve referencia em org_management.py
-- ====================================================================
CREATE OR REPLACE VIEW clinic_members AS
SELECT user_id, clinic_id, role AS clinic_role, is_default, created_at
FROM user_clinics;
