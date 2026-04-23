-- Down migration 036: dropa views e funcoes da migration 036.
--
-- Sem efeito em dados — views e funcoes sao estruturas auxiliares.
-- Codigo que dependa dessas views/funcoes vai falhar pos-rollback ate
-- ser ajustado para acessar as tabelas base diretamente.
--
-- Idempotente: todos os DROP usam IF EXISTS.
-- ============================================================================

DROP FUNCTION IF EXISTS fn_verify_chain_integrity(VARCHAR);
DROP FUNCTION IF EXISTS fn_generate_event_hash(JSONB, CHAR);

DROP VIEW IF EXISTS v_sandbox_indicator_dashboard;
DROP VIEW IF EXISTS v_traceability_chain_status;
DROP VIEW IF EXISTS v_member_active_prescriptions;


-- ============================================================================
-- Fim do down 036. Apos executar, remova manualmente o registro:
--   DELETE FROM schema_migrations WHERE version = '036';
-- ============================================================================
