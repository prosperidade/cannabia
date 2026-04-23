-- Migration 035: Indexes compostos e performance (F6.1 do docs/BACKLOG_SCC.md)
--
-- Adiciona indexes compostos cobrindo:
--   - doc 25 §13.2 explicito: (tenant_id, occurred_at DESC) em
--     traceability_events e (tenant_id, reported_at DESC) em adverse_events.
--   - queries quentes do Evidence Engine F4.1
--     (list_responded_followups, list_treatment_plans_by_condition).
--   - dashboard de farmacovigilancia com filtro por severidade.
--   - notificacoes pendentes em pharmacovigilance_notifications.
--   - ai_audit_logs como time-series por tenant.
--   - anchor upgrade job — varredura por status='pending'.
--   - sandbox_indicator_values lookup do mais recente por indicador.
--
-- NUMERACAO: o slot original F6.1 do docs/BACKLOG_SCC.md aponta para
-- "034_indexes_and_performance.sql", mas a migration 034 foi consumida
-- pelo bloco F4.7 (review_workflows) durante a sessao de 2026-04-21.
-- Esta migration ocupa o slot 035 — atualizar BACKLOG_SCC para refletir.
--
-- Idempotente: todos os indexes usam CREATE [UNIQUE] INDEX IF NOT EXISTS.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- 1. traceability_events — dashboards por tenant ordenados por tempo
--    doc 25 §13.2 explicito.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_trace_tenant_occurred
    ON traceability_events (tenant_id, occurred_at DESC);

-- Dashboards filtrados por tipo de evento (plantio, colheita, dispensacao):
CREATE INDEX IF NOT EXISTS idx_trace_tenant_type_occurred
    ON traceability_events (tenant_id, event_type, occurred_at DESC);


-- ---------------------------------------------------------------------------
-- 2. adverse_events — dashboards epidemiologicos
--    doc 25 §13.2 explicito + filtro por severidade.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_ae_tenant_reported
    ON adverse_events (tenant_id, reported_at DESC);

CREATE INDEX IF NOT EXISTS idx_ae_tenant_severity_reported
    ON adverse_events (tenant_id, severity, reported_at DESC);


-- ---------------------------------------------------------------------------
-- 3. pharmacovigilance_notifications — pendentes de resposta da ANVISA
--    Partial: WHERE response_received_at IS NULL — minimiza tamanho.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_pv_notif_pending
    ON pharmacovigilance_notifications (notification_target, notified_at DESC)
    WHERE response_received_at IS NULL;


-- ---------------------------------------------------------------------------
-- 4. scheduled_followups — query quente do Evidence Engine F4.1
--    list_responded_followups filtra por clinic_id + responded_at IS NOT NULL.
--    Partial index pega so as linhas que importam para agregacao.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_followup_responded
    ON scheduled_followups (clinic_id, responded_at DESC)
    WHERE responded_at IS NOT NULL;


-- ---------------------------------------------------------------------------
-- 5. treatment_plans — F4.1 + dashboards "planos ativos por clinica"
--    Composite (clinic_id, status, created_at DESC) cobre tanto a query
--    list_treatment_plans_by_condition quanto listagens administrativas.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_treatment_plans_clinic_status_created
    ON treatment_plans (clinic_id, status, created_at DESC);


-- ---------------------------------------------------------------------------
-- 6. ai_audit_logs como time-series por tenant
--    Complementa os GIN indexes em input_payload/output_payload (022).
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_ai_audit_logs_clinic_created
    ON ai_audit_logs (clinic_id, created_at DESC);


-- ---------------------------------------------------------------------------
-- 7. blockchain_anchors — anchor_upgrade_service hot path
--    Partial: so pendentes (verification_status='pending') sao varridos
--    pelo job; demais sao acesso pontual via outros indexes.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_anchors_pending
    ON blockchain_anchors (tenant_id, anchored_at)
    WHERE verification_status = 'pending';


-- ---------------------------------------------------------------------------
-- 8. sandbox_indicator_values — lookup do valor mais recente por indicador
--    "qual o ultimo valor desse indicador" e operacao comum em dashboards.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_siv_indicator_period_desc
    ON sandbox_indicator_values (indicator_id, period_start DESC);


-- ---------------------------------------------------------------------------
-- 9. symptom_diary scoped por tenant
--    O index existente (patient_id, created_at DESC) cobre queries
--    por paciente. Para dashboards "todos os diarios da clinica nas
--    ultimas N horas", precisamos de tenant scope.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_symptom_diary_clinic_created
    ON symptom_diary (clinic_id, created_at DESC);


-- ============================================================================
-- Fim da migration 035. O runner registra versao e checksum em
-- schema_migrations; nao e necessario INSERT manual aqui.
-- ============================================================================
