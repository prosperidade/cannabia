-- Down migration 034: reverter Document Review Workflows (F4.7)
--
-- Reverte em ordem inversa a criacao:
--   - DROP trigger append-only (nao dropa prevent_update_delete porque
--     ela e compartilhada com 027, 030 e possivelmente futuras).
--   - DROP TABLE document_review_workflows.
--   - ALTER TABLE regulatory_reports: DROP constraint + DROP colunas.
--
-- ATENCAO — perda informacional:
--
-- Dropar document_review_workflows apaga a TRILHA DE AUDITORIA de
-- aprovacoes bilaterais. As assinaturas eletronicas (signature_hash) e
-- as transicoes de estado ficam perdidas localmente. Em ambiente com
-- dados reais, o caminho oficial e restore por backup — ver
-- docs/BACKUP_AND_DISASTER_RECOVERY.md §4.
--
-- Idempotente: IF EXISTS em tudo.
-- ============================================================================

-- Trigger
DROP TRIGGER IF EXISTS trg_review_workflows_append_only
    ON document_review_workflows;

-- Tabela
DROP TABLE IF EXISTS document_review_workflows;

-- Constraint e colunas em regulatory_reports
ALTER TABLE regulatory_reports
    DROP CONSTRAINT IF EXISTS chk_reg_reports_status;

ALTER TABLE regulatory_reports
    DROP COLUMN IF EXISTS current_stage_notes;

ALTER TABLE regulatory_reports
    DROP COLUMN IF EXISTS status;


-- ============================================================================
-- Fim do down 034. Apos executar, remova manualmente o registro:
--   DELETE FROM schema_migrations WHERE version = '034';
-- ============================================================================
