-- Down migration 024: reverter tenants evolution
--
-- Reverte os ADD COLUMN, CHECK constraints e indexes aplicados pela
-- up-migration 024_tenants_evolution.sql.
--
-- ATENCAO — perda informacional:
--
-- Dropar as colunas `trade_name`, `cnpj`, `incorporation_date`, `plan_tier`,
-- `whitelabel_config` e `tenant_type` **descarta** os valores armazenados.
-- Se esses dados foram preenchidos em produto (entrada de usuario), o down
-- os perde. Use com cautela em ambientes com dados reais; o caminho oficial
-- para voltar a um estado anterior com dados e restore por backup — ver
-- docs/BACKUP_AND_DISASTER_RECOVERY.md §4.
--
-- `is_active` e coluna gerada (sem dados proprios); sua remocao nao perde
-- informacao — `status` continua sendo a fonte de verdade.
--
-- `billing_plan` e `tenant_type_id` nao sao tocados aqui porque ja existiam
-- antes da 024. Permanecem intactos no banco.
--
-- Idempotente: todos os DROPs usam IF EXISTS.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------
DROP INDEX IF EXISTS idx_tenants_plan_tier;
DROP INDEX IF EXISTS idx_tenants_type;
DROP INDEX IF EXISTS uq_tenants_cnpj;


-- ---------------------------------------------------------------------------
-- CHECK constraints
-- ---------------------------------------------------------------------------
ALTER TABLE tenants DROP CONSTRAINT IF EXISTS chk_tenants_plan_tier;
ALTER TABLE tenants DROP CONSTRAINT IF EXISTS chk_tenants_type;


-- ---------------------------------------------------------------------------
-- Colunas adicionadas pela 024
-- ---------------------------------------------------------------------------
ALTER TABLE tenants DROP COLUMN IF EXISTS is_active;
ALTER TABLE tenants DROP COLUMN IF EXISTS whitelabel_config;
ALTER TABLE tenants DROP COLUMN IF EXISTS plan_tier;
ALTER TABLE tenants DROP COLUMN IF EXISTS incorporation_date;
ALTER TABLE tenants DROP COLUMN IF EXISTS cnpj;
ALTER TABLE tenants DROP COLUMN IF EXISTS trade_name;
ALTER TABLE tenants DROP COLUMN IF EXISTS tenant_type;


-- ============================================================================
-- Fim do down 024. Apos executar, remova manualmente o registro:
--   DELETE FROM schema_migrations WHERE version = '024';
-- ============================================================================
