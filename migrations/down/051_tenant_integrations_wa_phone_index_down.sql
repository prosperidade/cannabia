-- Down de 051_tenant_integrations_wa_phone_index.sql
--
-- Remove o indice unico parcial de roteamento. Sem perda de dados.
--
-- Apos rodar este down, lembre de:
--   DELETE FROM schema_migrations WHERE version = '051';

DROP INDEX IF EXISTS uq_tenant_integrations_wa_phone_number_id;
