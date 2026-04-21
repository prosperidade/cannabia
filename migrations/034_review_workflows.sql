-- Migration 034: Document Review Workflows (F4.7 do docs/BACKLOG_SCC.md)
--
-- Adiciona fluxo de aprovacao bilateral previsto em doc 27 §§2.4 e 8.1:
--
--   draft → rt_review → legal_review → approved
--                                   ↘ rejected
--                   ↘ approved (rt_approve_final, pula legal)
--                   ↘ rejected
--
-- Mudancas:
--   1) ALTER regulatory_reports: coluna ``status`` com whitelist de 5
--      estados; coluna ``current_stage_notes`` opcional para registrar
--      comentario corrente.
--   2) CREATE document_review_workflows APPEND-ONLY — cada linha e um
--      step imutavel do fluxo com assinatura eletronica minima
--      (signature_hash SHA-256 de report_id + to_status + actor_user_id
--      + content_hash_at_review + reviewed_at ISO).
--   3) Reusa prevent_update_delete() criada em 027 para imutabilidade.
--
-- Idempotencia: ADD COLUMN IF NOT EXISTS + CREATE TABLE IF NOT EXISTS.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- 1. regulatory_reports: adicionar status
--
-- Coluna ``status`` defaulta 'draft' para rows existentes (relatorios ja
-- criados sem fluxo explicito entram como rascunho e podem ser
-- reavaliados pelo RT).
-- ---------------------------------------------------------------------------
ALTER TABLE regulatory_reports
    ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'draft';

ALTER TABLE regulatory_reports
    ADD COLUMN IF NOT EXISTS current_stage_notes TEXT;

-- CHECK da whitelist de estados. Idempotente via catalogo pg_constraint.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'chk_reg_reports_status'
    ) THEN
        ALTER TABLE regulatory_reports
            ADD CONSTRAINT chk_reg_reports_status CHECK (
                status IN ('draft', 'rt_review', 'legal_review',
                           'approved', 'rejected')
            );
    END IF;
END $$;


-- ---------------------------------------------------------------------------
-- 2. document_review_workflows (APPEND-ONLY)
--
-- Cada linha = 1 transicao de estado no fluxo do report. O conjunto
-- ordenado por reviewed_at e a trilha de auditoria. Pela natureza
-- append-only, edicao e delecao sao bloqueadas via trigger.
--
-- signature_hash e o SHA-256 de:
--   f"{report_id}:{from_status}:{to_status}:{action}:{actor_user_id}:
--     {content_hash_at_review}:{reviewed_at_iso}"
-- calculado no servico antes do INSERT. Permite verificacao posterior
-- recomputando a partir dos campos da linha.
--
-- content_hash_at_review guarda o SHA-256 do documento no momento do
-- review — se o documento for regerado com dados atualizados entre
-- reviews, o diff fica explicito comparando este hash com o
-- regulatory_reports.content_hash atual.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_review_workflows (
    id                     BIGSERIAL PRIMARY KEY,
    report_id              INT NOT NULL REFERENCES regulatory_reports(id),
    from_status            VARCHAR(32) NOT NULL,
    to_status              VARCHAR(32) NOT NULL,
    action                 VARCHAR(32) NOT NULL,
    actor_user_id          INT NOT NULL REFERENCES users(id),
    actor_role             VARCHAR(64) NOT NULL,
    notes                  TEXT,
    content_hash_at_review CHAR(64) NOT NULL,
    signature_hash         CHAR(64) NOT NULL,
    reviewed_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_review_status_from CHECK (
        from_status IN ('draft', 'rt_review', 'legal_review', 'rejected')
    ),
    CONSTRAINT chk_review_status_to CHECK (
        to_status IN ('rt_review', 'legal_review', 'approved', 'rejected')
    ),
    CONSTRAINT chk_review_action CHECK (
        action IN (
            'submit_to_rt',      -- draft|rejected → rt_review
            'rt_approve',        -- rt_review      → legal_review
            'rt_approve_final',  -- rt_review      → approved (pula legal)
            'rt_reject',         -- rt_review      → rejected
            'legal_approve',     -- legal_review   → approved
            'legal_reject'       -- legal_review   → rejected
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_review_workflows_report
    ON document_review_workflows (report_id);
CREATE INDEX IF NOT EXISTS idx_review_workflows_actor
    ON document_review_workflows (actor_user_id);
CREATE INDEX IF NOT EXISTS idx_review_workflows_reviewed_at
    ON document_review_workflows (reviewed_at);


-- ---------------------------------------------------------------------------
-- 3. Trigger APPEND-ONLY (reusa prevent_update_delete de 027)
--
-- Guard via pg_trigger para idempotencia. prevent_update_delete() ja
-- deve existir (criada em 027). Se nao existir, DO block falha cedo —
-- o que indica ordem incorreta de migrations.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'prevent_update_delete'
    ) THEN
        RAISE EXCEPTION
            'prevent_update_delete() nao existe — aplique migration 027 antes da 034.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
         WHERE tgname = 'trg_review_workflows_append_only'
    ) THEN
        CREATE TRIGGER trg_review_workflows_append_only
        BEFORE UPDATE OR DELETE ON document_review_workflows
        FOR EACH ROW EXECUTE FUNCTION prevent_update_delete();
    END IF;
END $$;


-- ============================================================================
-- Fim da migration 034.
-- ============================================================================
