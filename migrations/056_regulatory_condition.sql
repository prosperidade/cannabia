-- migrations/056_regulatory_condition.sql
-- Onda 2 / Track REG · REG-3 (docs/29.2 bloco regulatório; doc 30 §REG-CLÍNICO)
-- Campo estruturado "condição grave/debilitante / cuidados paliativos" na
-- prescrição, com justificativa textual do médico (auditada). É o pré-requisito
-- de elegibilidade para produtos com THC > 0,2% (REG-4, RDCs 2026).
--   * prescriptions.regulatory_condition  — nenhuma | grave_debilitante | paliativa
--   * prescriptions.clinical_justification — justificativa do médico (auditada)
-- B6: NUNCA bloqueia emissão — registro/auditoria; o médico é o decisor.
-- Aditiva e idempotente. Down em migrations/down/056_regulatory_condition_down.sql
-- ============================================================================

ALTER TABLE prescriptions
    ADD COLUMN IF NOT EXISTS regulatory_condition VARCHAR(30) NOT NULL DEFAULT 'nenhuma';

ALTER TABLE prescriptions
    ADD COLUMN IF NOT EXISTS clinical_justification TEXT;

-- Guarda de domínio defensiva (espelha o enum RegulatoryCondition em schemas.py).
-- Idempotente: só adiciona a constraint se ainda não existir.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_prescriptions_regulatory_condition'
    ) THEN
        ALTER TABLE prescriptions
            ADD CONSTRAINT ck_prescriptions_regulatory_condition
            CHECK (regulatory_condition IN ('nenhuma', 'grave_debilitante', 'paliativa'));
    END IF;
END $$;
