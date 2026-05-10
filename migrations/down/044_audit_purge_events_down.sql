-- Down de 044_audit_purge_events.sql

DROP INDEX IF EXISTS idx_ai_audit_purge_processed_event;
DROP TABLE IF EXISTS ai_audit_purge_processed_ids CASCADE;
DROP TABLE IF EXISTS ai_audit_purge_events CASCADE;
