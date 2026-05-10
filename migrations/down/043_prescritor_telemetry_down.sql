-- Down de 043_prescritor_telemetry.sql

ALTER TABLE ai_audit_logs
  DROP COLUMN IF EXISTS prescription_time_ms,
  DROP COLUMN IF EXISTS prescription_input_tokens,
  DROP COLUMN IF EXISTS prescription_output_tokens;
