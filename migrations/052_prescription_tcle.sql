-- migrations/052_prescription_tcle.sql
-- Track B / REG-1015 (doc 30 Onda 1; RDC 1.015/2026 — JÁ EM VIGOR)
-- Prontidão mínima vigente no fluxo de prescrição: registro de TCLE (termo de
-- consentimento livre e esclarecido) vinculado à prescrição + snapshot da
-- validação de prescritor habilitado. Schema mínimo + ponto de captura; a UI
-- completa e a validação plena do conselho ficam para depois (pendência de
-- revalidação contra o inteiro teor da RDC 1.015 — PDF escaneado lido via RAG).
-- Linguagem: PRONTIDÃO regulatória, nunca aprovação.
-- Aditiva e idempotente. Down em migrations/down/052_prescription_tcle_down.sql
-- ============================================================================

CREATE TABLE IF NOT EXISTS prescription_consents (
    id                    SERIAL PRIMARY KEY,
    clinic_id             INT          NOT NULL,
    prescription_id       INT          NOT NULL,
    patient_id            INT          NOT NULL,
    prescriber_user_id    INT,
    prescriber_crm        VARCHAR(40),
    prescriber_habilitado BOOLEAN      NOT NULL DEFAULT FALSE,
    -- NULL = TCLE ainda pendente de captura (fluxo de assinatura é UI futura)
    tcle_accepted         BOOLEAN,
    tcle_version          VARCHAR(80)  NOT NULL DEFAULT 'RDC-1.015/2026-min',
    norm_ref              VARCHAR(40)  NOT NULL DEFAULT 'RDC 1.015/2026',
    pending_revalidation  BOOLEAN      NOT NULL DEFAULT TRUE,
    details               JSONB,
    captured_at           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_prescription_consents_prescription
    ON prescription_consents (prescription_id);
CREATE INDEX IF NOT EXISTS idx_prescription_consents_clinic
    ON prescription_consents (clinic_id);
