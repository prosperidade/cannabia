-- Down de 055_inbound_idempotency.sql
--
-- Remove os indices unicos e a coluna wamid. Os valores de wamid ja gravados e
-- a deduplicacao de conversation_messages (ETAPA 2 do UP) NAO sao revertidos —
-- perda irreversivel por natureza (linhas duplicadas apagadas nao retornam).
--
-- Apos rodar este down, lembre de:
--   DELETE FROM schema_migrations WHERE version = '055';

DROP INDEX IF EXISTS uq_conversation_messages_external_id;
DROP INDEX IF EXISTS uq_incoming_messages_clinic_wamid;
ALTER TABLE incoming_messages DROP COLUMN IF EXISTS wamid;
