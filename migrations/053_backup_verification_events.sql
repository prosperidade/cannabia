-- Migration 053: Heartbeat/auditoria das verificacoes de backup.
--
-- OBS-1 (doc 30 OBS-1 / 29.5 R12 / BUG-001) — fecha o modo de falha que
-- materializou o incidente de 14/05: backup que falha SILENCIOSAMENTE (dumps
-- de 0 bytes de 11/05 que ninguem percebeu ate o volume ser apagado).
--
-- backup_verification_events: cada execucao da verificacao tripla
-- (scripts/backup_verify.py) grava uma linha aqui — sucesso OU falha. Isso
-- transforma falha silenciosa em falha VISIVEL: um monitor de heartbeat
-- alerta quando nao ha linha success=TRUE recente (doc 30 §5: "historico de
-- falha silenciosa em jobs recomenda alerta de heartbeat").
--
-- Espelha o padrao de ai_audit_purge_events (migration 044).

CREATE TABLE IF NOT EXISTS backup_verification_events (
  id SERIAL PRIMARY KEY,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  dump_path TEXT,
  dump_bytes BIGINT,
  restore_list_lines INTEGER,
  sample_restore_ddl_lines INTEGER,
  sha256 TEXT,
  success BOOLEAN NOT NULL DEFAULT FALSE,
  executor_host TEXT,
  error_message TEXT
);

COMMENT ON TABLE backup_verification_events IS 'Heartbeat/auditoria da verificacao tripla de backup (OBS-1, doc 30). Falha = linha com success=FALSE; ausencia de success recente = alerta de heartbeat.';
COMMENT ON COLUMN backup_verification_events.success IS 'TRUE so quando os 3 gates passam: tamanho>limiar, pg_restore --list, restauracao de amostra (--schema-only)';
COMMENT ON COLUMN backup_verification_events.sample_restore_ddl_lines IS 'Statements DDL reconstruidos pela restauracao de amostra (3o gate)';

CREATE INDEX IF NOT EXISTS idx_backup_verification_started
  ON backup_verification_events (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_backup_verification_success
  ON backup_verification_events (success, started_at DESC);
