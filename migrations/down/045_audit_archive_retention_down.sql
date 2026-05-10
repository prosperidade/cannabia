-- Down de 045_audit_archive_retention.sql

DROP INDEX IF EXISTS idx_ai_audit_logs_created_at_status;
DROP TABLE IF EXISTS ai_audit_logs_archive CASCADE;
