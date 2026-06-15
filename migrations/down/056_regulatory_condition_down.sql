-- Down de 056_regulatory_condition.sql
--
-- Remove a constraint de domínio e as colunas regulatory_condition e
-- clinical_justification de prescriptions. Os valores já gravados nessas
-- colunas são perdidos — irreversível por natureza.
--
-- Após rodar este down, lembre de:
--   DELETE FROM schema_migrations WHERE version = '056';

ALTER TABLE prescriptions DROP CONSTRAINT IF EXISTS ck_prescriptions_regulatory_condition;
ALTER TABLE prescriptions DROP COLUMN IF EXISTS clinical_justification;
ALTER TABLE prescriptions DROP COLUMN IF EXISTS regulatory_condition;
