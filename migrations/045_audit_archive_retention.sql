-- Migration 045: Archive table + index para retention policy.
--
-- Sprint 2 Track LGPD — fecha Divida 2 do BACKLOG_LGPD.md (retention policy
-- automatizada via Render Cron Job — pg_cron NAO esta disponivel no plano
-- basic-256mb do Postgres no Render).
--
-- ai_audit_logs_archive: cold storage de logs aposentados pelo retention.
--   Estrategia archive-then-delete: rows que ultrapassam o prazo (90d
--   detail / 365d critical) sao copiadas para o archive (com archived_at)
--   e depois removidas do hot table. Habilita forensics + auditabilidade
--   pos-fato sem inflar custo de IO em ai_audit_logs (consultado por
--   dashboards a cada request).
--
-- idx_ai_audit_logs_created_at_status: indice composto critico para o
--   filtro do retention. Sem isso o DELETE diario faz seqscan em
--   ai_audit_logs e degrada o DB enquanto roda.

-- Clona estrutura inteira (incluindo defaults, constraints e indexes
-- proprios). NUNCA usar PARTITION OF aqui — o objetivo eh fisica
-- separada, nao slicing logico.
CREATE TABLE IF NOT EXISTS ai_audit_logs_archive (LIKE ai_audit_logs INCLUDING ALL);

-- ALTER TABLE ADD COLUMN IF NOT EXISTS pra ser idempotente em re-runs.
ALTER TABLE ai_audit_logs_archive
  ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

COMMENT ON TABLE ai_audit_logs_archive IS 'Cold storage de ai_audit_logs aposentados pelo retention (Sprint 2 Track LGPD). Cleanup automatico apos LGPD_AUDIT_ARCHIVE_RETENTION_DAYS (default 5y).';
COMMENT ON COLUMN ai_audit_logs_archive.archived_at IS 'Timestamp de quando o row foi movido pro archive (usado pelo cleanup do archive)';

-- Index composto para o filtro do retention (created_at + status).
-- Cobre tanto o detail (90d default) quanto o critical (365d default,
-- status IN ('security_blocked','error')).
CREATE INDEX IF NOT EXISTS idx_ai_audit_logs_created_at_status
  ON ai_audit_logs(created_at, status);
