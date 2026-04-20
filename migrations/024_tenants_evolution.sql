-- Migration 024: Tenants Evolution (F1.1 do docs/BACKLOG_SCC.md)
--
-- Evolui a tabela `tenants` com os campos exigidos pelo Sandbox
-- Compliance Core, conforme `docs/25_SCC_DATA_MODEL_AND_MIGRATIONS.md`
-- Seção 4.1 e a estratégia de retrocompatibilidade de Seção 11.3:
--
--   - `tenant_type`         VARCHAR CHECK — discriminador (clinic/association/doctor).
--                           Denormalizacao de tenant_type_id para CHECKs rapidos e
--                           queries que nao precisam do JOIN em tenant_types.
--   - `trade_name`          VARCHAR — nome fantasia (backfill de display_name).
--   - `cnpj`                VARCHAR(14) — UNIQUE partial (ignora NULL/vazio).
--   - `incorporation_date`  DATE — data de constituicao.
--   - `plan_tier`           VARCHAR CHECK — plano do SCC (basic/pro/premium/
--                           sandbox_ready). Backfill mapeado a partir de billing_plan.
--   - `whitelabel_config`   JSONB — configuracao whitelabel por tenant.
--   - `is_active`           BOOLEAN GENERATED ALWAYS AS (status = 'active') STORED —
--                           espelho derivado de status, requerido pelo doc 25 §4.1.
--
-- Nenhuma coluna existente e dropada. `tenant_type_id` permanece como fonte de
-- verdade relacional para a tabela `tenant_types`; `tenant_type` e a
-- denormalizacao mantida em sincronia pela aplicacao (repositorio de tenants).
-- `billing_plan` permanece para compatibilidade com codigo existente; `plan_tier`
-- passa a ser o campo canonico do SCC.
--
-- Idempotente: todos os ADD COLUMN usam IF NOT EXISTS; constraints via DO $$ que
-- consulta pg_constraint; indexes via CREATE ... IF NOT EXISTS.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. tenant_type (denormalizacao com CHECK whitelist)
-- ---------------------------------------------------------------------------
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS tenant_type VARCHAR(32);

-- Backfill a partir de tenant_types.slug
UPDATE tenants t
   SET tenant_type = tt.slug
  FROM tenant_types tt
 WHERE t.tenant_type_id = tt.id
   AND t.tenant_type IS NULL;

-- Defensive fallback: linhas sem slug resoluvel viram 'clinic' (caso mais comum
-- em dados legados). Garante SET NOT NULL logo abaixo.
UPDATE tenants SET tenant_type = 'clinic' WHERE tenant_type IS NULL;

ALTER TABLE tenants ALTER COLUMN tenant_type SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_tenants_type'
    ) THEN
        ALTER TABLE tenants
          ADD CONSTRAINT chk_tenants_type
          CHECK (tenant_type IN ('clinic', 'association', 'doctor'));
    END IF;
END
$$;


-- ---------------------------------------------------------------------------
-- 2. trade_name (nome fantasia) — backfill de display_name
-- ---------------------------------------------------------------------------
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS trade_name VARCHAR(255);

UPDATE tenants
   SET trade_name = display_name
 WHERE trade_name IS NULL;


-- ---------------------------------------------------------------------------
-- 3. cnpj — UNIQUE partial
-- ---------------------------------------------------------------------------
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS cnpj VARCHAR(14);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tenants_cnpj
    ON tenants (cnpj)
    WHERE cnpj IS NOT NULL AND cnpj <> '';


-- ---------------------------------------------------------------------------
-- 4. incorporation_date
-- ---------------------------------------------------------------------------
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS incorporation_date DATE;


-- ---------------------------------------------------------------------------
-- 5. plan_tier — CHECK whitelist + backfill a partir de billing_plan
-- ---------------------------------------------------------------------------
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS plan_tier VARCHAR(32);

-- Mapeia billing_plan legado para plan_tier do SCC:
--   'starter' -> 'basic'; 'basic'/'pro'/'premium'/'sandbox_ready' -> preservado;
--   qualquer outro (nao esperado) -> 'basic' defensivo.
UPDATE tenants
   SET plan_tier = CASE
                     WHEN billing_plan = 'starter' THEN 'basic'
                     WHEN billing_plan IN ('basic', 'pro', 'premium', 'sandbox_ready')
                         THEN billing_plan
                     ELSE 'basic'
                   END
 WHERE plan_tier IS NULL;

ALTER TABLE tenants ALTER COLUMN plan_tier SET DEFAULT 'basic';
ALTER TABLE tenants ALTER COLUMN plan_tier SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_tenants_plan_tier'
    ) THEN
        ALTER TABLE tenants
          ADD CONSTRAINT chk_tenants_plan_tier
          CHECK (plan_tier IN ('basic', 'pro', 'premium', 'sandbox_ready'));
    END IF;
END
$$;


-- ---------------------------------------------------------------------------
-- 6. whitelabel_config JSONB
-- ---------------------------------------------------------------------------
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS whitelabel_config JSONB;


-- ---------------------------------------------------------------------------
-- 7. is_active — coluna gerada a partir de status.
-- Requerida pelo doc 25 §4.1. GENERATED ALWAYS STORED garante que o valor e
-- recomputado automaticamente a cada UPDATE em status (fonte de verdade).
-- ---------------------------------------------------------------------------
ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN
    GENERATED ALWAYS AS (status = 'active') STORED;


-- ---------------------------------------------------------------------------
-- 8. Indexes conforme doc 25 §4.1
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_tenants_type ON tenants (tenant_type);
CREATE INDEX IF NOT EXISTS idx_tenants_plan_tier ON tenants (plan_tier);


-- ============================================================================
-- Fim da migration 024. O runner registra versao e checksum em
-- schema_migrations; nao e necessario INSERT manual aqui.
-- ============================================================================
