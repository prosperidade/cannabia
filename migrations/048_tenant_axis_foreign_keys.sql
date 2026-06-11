-- migrations/048_tenant_axis_foreign_keys.sql
-- TEN-1 (doc 30 Onda 1 / docs/29.1 R2): Integridade referencial do EIXO TENANT.
--
-- A migration 004 criou a ponte clinic_id -> tenant_id (clinics.tenant_id) e a
-- tabela de papeis por tenant (user_tenant_roles), MAS sem nenhuma FK. O 29.1
-- classificou isso como risco C4: orfaos silenciosos no eixo central de tenancy.
-- Esta migration adiciona as 3 FKs faltantes, com limpeza de orfaos antes
-- (padrao da 007) e DO $$ idempotente consultando pg_constraint (padrao da 024).
--
-- Politica de ON DELETE:
--   - clinics.tenant_id -> tenants(id): ON DELETE SET NULL. A coluna e a ponte
--     nullable e transitoria (legado clinic_id-only convive com tenant_id, ver
--     INV-2 do doc 30). Remover um tenant NAO pode apagar a clinica nem seus
--     dados clinicos; apenas desfaz o vinculo. (Divergencia consciente do
--     RESTRICT generico da 007 — justificada pela natureza nullable da ponte.)
--   - user_tenant_roles.{user_id,tenant_id}: ON DELETE CASCADE. Tabela de
--     juncao/papeis (apoio); remover o user ou o tenant remove os vinculos
--     correspondentes (padrao da 007 para tabelas de apoio).
--
-- Indices: idx_clinics_tenant_id e idx_user_tenant_roles_tenant_id ja existem
-- (004); user_tenant_roles.user_id e a coluna lider da PK composta
-- (user_id, tenant_id, role), portanto ja indexada. Nenhum indice novo.
--
-- Idempotente: limpeza e re-executavel; FKs via DO $$ que verifica pg_constraint.
-- Down: migrations/down/048_tenant_axis_foreign_keys_down.sql (UP->DOWN->UP testado).
-- ============================================================================

-- ---------------------------------------------------------------------------
-- ETAPA 1 — Limpeza de orfaos ANTES das constraints
-- ---------------------------------------------------------------------------

-- clinics.tenant_id -> tenants : orfao vira NULL (preserva a clinica)
UPDATE clinics
   SET tenant_id = NULL
 WHERE tenant_id IS NOT NULL
   AND tenant_id NOT IN (SELECT id FROM tenants);

-- user_tenant_roles -> users : remove vinculo de usuario inexistente
DELETE FROM user_tenant_roles
 WHERE user_id NOT IN (SELECT id FROM users);

-- user_tenant_roles -> tenants : remove vinculo de tenant inexistente
DELETE FROM user_tenant_roles
 WHERE tenant_id NOT IN (SELECT id FROM tenants);

-- ---------------------------------------------------------------------------
-- ETAPA 2 — FKs idempotentes
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_clinics_tenant_id'
    ) THEN
        ALTER TABLE clinics
          ADD CONSTRAINT fk_clinics_tenant_id
          FOREIGN KEY (tenant_id) REFERENCES tenants(id)
          ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_user_tenant_roles_user'
    ) THEN
        ALTER TABLE user_tenant_roles
          ADD CONSTRAINT fk_user_tenant_roles_user
          FOREIGN KEY (user_id) REFERENCES users(id)
          ON DELETE CASCADE;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_user_tenant_roles_tenant'
    ) THEN
        ALTER TABLE user_tenant_roles
          ADD CONSTRAINT fk_user_tenant_roles_tenant
          FOREIGN KEY (tenant_id) REFERENCES tenants(id)
          ON DELETE CASCADE;
    END IF;
END
$$;
