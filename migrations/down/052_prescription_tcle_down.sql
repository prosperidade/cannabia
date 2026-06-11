-- Down de 052_prescription_tcle.sql
--
-- Remove a tabela de TCLE/consentimento de prescrição (e seus índices). Os
-- registros de consentimento gravados são perdidos — irreversível por natureza.
--
-- Apos rodar este down, lembre de:
--   DELETE FROM schema_migrations WHERE version = '052';

DROP TABLE IF EXISTS prescription_consents;
