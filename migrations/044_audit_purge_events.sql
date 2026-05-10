-- Migration 044: Tabelas de eventos de purge LGPD.
--
-- Sprint 2 Track LGPD — fecha Divida 1 do BACKLOG_LGPD.md (purge retroativo
-- de PII em ai_audit_logs gravada antes do merge de A.3, commit aae1237).
--
-- ai_audit_purge_events: audit trail de cada execucao do purge, com cutoff,
--   dry-run flag, contagens e error summary. Indispensavel pra LGPD demonstrar
--   "quando, como, quanto" cada operacao de descarte/sanitizacao foi feita.
--
-- ai_audit_purge_processed_ids: dedup table pra resume support. Sem isso o
--   script poderia re-processar rows ja sanitizadas em re-runs apos falha,
--   degradando metricas e custando IO desnecessario.

CREATE TABLE IF NOT EXISTS ai_audit_purge_events (
  id SERIAL PRIMARY KEY,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  cutoff_timestamp TIMESTAMPTZ NOT NULL,
  rows_scanned INTEGER NOT NULL DEFAULT 0,
  rows_updated INTEGER NOT NULL DEFAULT 0,
  rows_failed INTEGER NOT NULL DEFAULT 0,
  executor_user TEXT,
  executor_host TEXT,
  dry_run BOOLEAN NOT NULL DEFAULT TRUE,
  batch_size INTEGER NOT NULL DEFAULT 1000,
  error_summary TEXT
);

COMMENT ON TABLE ai_audit_purge_events IS 'Audit trail dos eventos de purge LGPD em ai_audit_logs (Sprint 2 Track LGPD)';
COMMENT ON COLUMN ai_audit_purge_events.cutoff_timestamp IS 'Timestamp de corte: rows com created_at < cutoff foram alvo do purge';
COMMENT ON COLUMN ai_audit_purge_events.dry_run IS 'TRUE quando script rodado em --dry-run; FALSE em --commit (mutacao real)';
COMMENT ON COLUMN ai_audit_purge_events.executor_host IS 'Hostname (ou ''cron'' para retention_audit_logs.py em Render Cron Job)';

CREATE TABLE IF NOT EXISTS ai_audit_purge_processed_ids (
  audit_log_id INTEGER PRIMARY KEY,
  purge_event_id INTEGER REFERENCES ai_audit_purge_events(id),
  processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE ai_audit_purge_processed_ids IS 'Dedup table do purge LGPD: garante idempotencia em re-runs/resume apos falha';

CREATE INDEX IF NOT EXISTS idx_ai_audit_purge_processed_event
  ON ai_audit_purge_processed_ids(purge_event_id);
