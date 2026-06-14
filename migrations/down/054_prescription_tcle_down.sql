-- Down de 054_prescription_tcle.sql
--
-- Remove a tabela de TCLE/consentimento de prescrição (e seus índices). Os
-- registros de consentimento gravados são perdidos — irreversível por natureza.
--
-- Apos rodar este down, lembre de:
--   DELETE FROM schema_migrations WHERE version = '054';

DROP TABLE IF EXISTS prescription_consents;
