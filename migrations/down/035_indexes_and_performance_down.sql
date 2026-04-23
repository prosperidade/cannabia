-- Down migration 035: dropa os indexes compostos adicionados.
--
-- Sem efeito em dados — indexes sao estruturas auxiliares de
-- performance. Pos-rollback, queries continuam funcionando, apenas
-- com plans menos eficientes.
--
-- Idempotente: todos os DROP usam IF EXISTS.
-- ============================================================================

DROP INDEX IF EXISTS idx_symptom_diary_clinic_created;
DROP INDEX IF EXISTS idx_siv_indicator_period_desc;
DROP INDEX IF EXISTS idx_anchors_pending;
DROP INDEX IF EXISTS idx_ai_audit_logs_clinic_created;
DROP INDEX IF EXISTS idx_treatment_plans_clinic_status_created;
DROP INDEX IF EXISTS idx_followup_responded;
DROP INDEX IF EXISTS idx_pv_notif_pending;
DROP INDEX IF EXISTS idx_ae_tenant_severity_reported;
DROP INDEX IF EXISTS idx_ae_tenant_reported;
DROP INDEX IF EXISTS idx_trace_tenant_type_occurred;
DROP INDEX IF EXISTS idx_trace_tenant_occurred;


-- ============================================================================
-- Fim do down 035. Apos executar, remova manualmente o registro:
--   DELETE FROM schema_migrations WHERE version = '035';
-- ============================================================================
