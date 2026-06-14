-- Down de 053_backup_verification_events.sql
--
-- Reversao NAO-destrutiva de dados de producao (a tabela so guarda metadados
-- de verificacao de backup, descartaveis). Dropa tabela + indices.
--
-- Apos rodar este down, lembre de:
--   DELETE FROM schema_migrations WHERE version = '053';
-- (ver migrations/down/README.md)

DROP INDEX IF EXISTS idx_backup_verification_success;
DROP INDEX IF EXISTS idx_backup_verification_started;
DROP TABLE IF EXISTS backup_verification_events;
