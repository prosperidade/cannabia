-- Down migration 022: reverter integrity hardening
--
-- Reverte os 8 ajustes aplicados por migrations/022_integrity_hardening.sql:
--   - UNIQUE case-insensitive em users.email (uq_users_email_lower)
--   - UNIQUE em triage_links.token_hash (uq_triage_links_token_hash)
--     + recria o indice nao-unico original `idx_triage_links_token_hash`
--       que a migration 022 removeu apos criar o UNIQUE.
--   - FK patients.user_id -> users(id) (fk_patients_user)
--   - CHECKs em patients.status / treatment_plans.status /
--     anamnesis_reports.status
--   - GIN em ai_audit_logs.input_payload / output_payload
--
-- Nao reverte a normalizacao defensiva executada pela 022 (orfaos em
-- patients.user_id que foram zerados para NULL, status fora do whitelist
-- que foram convertidos para 'ativo'/'pendente'). Esses ajustes sao
-- irreversiveis via SQL DDL: os valores originais foram descartados no
-- momento da aplicacao da up-migration. Recuperar esses dados exige
-- restauracao por backup (ver docs/BACKUP_AND_DISASTER_RECOVERY.md).
--
-- Idempotente: todos os DROPs usam IF EXISTS.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- GIN indexes em ai_audit_logs
-- ---------------------------------------------------------------------------
DROP INDEX IF EXISTS idx_ai_audit_logs_input_payload_gin;
DROP INDEX IF EXISTS idx_ai_audit_logs_output_payload_gin;


-- ---------------------------------------------------------------------------
-- CHECK constraints
-- ---------------------------------------------------------------------------
ALTER TABLE anamnesis_reports DROP CONSTRAINT IF EXISTS chk_anamnesis_reports_status;
ALTER TABLE treatment_plans   DROP CONSTRAINT IF EXISTS chk_treatment_plans_status;
ALTER TABLE patients          DROP CONSTRAINT IF EXISTS chk_patients_status;


-- ---------------------------------------------------------------------------
-- FK patients.user_id -> users(id)
-- ---------------------------------------------------------------------------
ALTER TABLE patients DROP CONSTRAINT IF EXISTS fk_patients_user;


-- ---------------------------------------------------------------------------
-- UNIQUE em triage_links.token_hash + restauracao do indice nao-unico
-- original criado em migrations/018_triage_links.sql.
-- ---------------------------------------------------------------------------
DROP INDEX IF EXISTS uq_triage_links_token_hash;
CREATE INDEX IF NOT EXISTS idx_triage_links_token_hash ON triage_links (token_hash);


-- ---------------------------------------------------------------------------
-- UNIQUE case-insensitive parcial em users.email
-- ---------------------------------------------------------------------------
DROP INDEX IF EXISTS uq_users_email_lower;


-- ============================================================================
-- Fim do down 022. Apos executar, remova manualmente o registro:
--   DELETE FROM schema_migrations WHERE version = '022';
-- ============================================================================
