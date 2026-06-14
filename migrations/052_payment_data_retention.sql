-- Migration 052: Retencao/expurgo LGPD do trilho de pagamento.
-- (numerada 052 para nao colidir com as migrations 050/051 da Track B —
--  inbound_idempotency / wa_phone_index — em execucao paralela; ver PR.)
--
-- FIN-2 (doc 30 R2 / 29.6 R2 / 29.6 C2) — minimizacao de dados pessoais
-- financeiros em repouso. Alinhada ao padrao das migrations 044/045
-- (ai_audit_purge_events / retention_audit_logs.py).
--
-- O job scripts/retention_payment_data.py expurga, apos a janela de retencao
-- (default 90d), os campos que carregam PII bruta do PSP:
--   - payment_transactions.raw_payload  -> '{}'::JSONB
--   - payment_webhook_log.body/headers  -> '{}'::JSONB (+ error_message NULL)
-- preservando os registros (ledger financeiro + metadados de auditoria) sem o
-- payload sensivel. payer_document ja entra mascarado na gravacao (FIN-2).
--
-- payment_data_purge_events: trilha auditavel de cada execucao do expurgo,
--   com cutoff, dry-run flag, contagens e error summary — espelha
--   ai_audit_purge_events (migration 044). Indispensavel para LGPD demonstrar
--   "quando, como, quanto" cada expurgo foi feito + heartbeat do job.

CREATE TABLE IF NOT EXISTS payment_data_purge_events (
  id SERIAL PRIMARY KEY,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  cutoff_timestamp TIMESTAMPTZ NOT NULL,
  tx_payloads_redacted INTEGER NOT NULL DEFAULT 0,
  webhook_logs_redacted INTEGER NOT NULL DEFAULT 0,
  rows_failed INTEGER NOT NULL DEFAULT 0,
  executor_user TEXT,
  executor_host TEXT,
  dry_run BOOLEAN NOT NULL DEFAULT TRUE,
  retention_days INTEGER NOT NULL DEFAULT 90,
  error_summary TEXT
);

COMMENT ON TABLE payment_data_purge_events IS 'Audit trail dos expurgos LGPD do trilho de pagamento (FIN-2, doc 30 R2). Espelha ai_audit_purge_events.';
COMMENT ON COLUMN payment_data_purge_events.cutoff_timestamp IS 'Timestamp de corte: rows com received_at < cutoff foram alvo do expurgo';
COMMENT ON COLUMN payment_data_purge_events.dry_run IS 'TRUE quando rodado em --dry-run; FALSE em --commit (mutacao real)';
COMMENT ON COLUMN payment_data_purge_events.executor_host IS 'Hostname (ou ''cron'' para retention_payment_data.py em Render Cron Job)';

-- Indices para o filtro do expurgo (received_at). payment_webhook_log ja
-- possui idx (provider, received_at); payment_transactions nao tinha indice
-- por received_at — o expurgo diario faria seqscan sem ele.
CREATE INDEX IF NOT EXISTS idx_payment_transactions_received
  ON payment_transactions (received_at);
