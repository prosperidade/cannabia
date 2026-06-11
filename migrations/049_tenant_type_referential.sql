-- migrations/049_tenant_type_referential.sql
-- TEN-2 (doc 30 Onda 1 / docs/29.1 R5/A1): Discriminador de tenant EXTENSIVEL.
--
-- A 024 adicionou tenants.tenant_type com CHECK literal restrito a
-- ('clinic','association','doctor'). Adicionar um tipo novo exigia DROP+ADD do
-- CHECK (nova migration). Esta migration troca o CHECK literal por validacao
-- REFERENCIAL: FK tenants.tenant_type -> tenant_types(slug). A partir daqui,
-- um tipo novo passa a ser um INSERT em tenant_types — sem migration de schema.
--
-- Tambem SEMEIA os tipos futuros (pharmacy, cultivator, lawfirm, research) no
-- catalogo tenant_types, SEM ativa-los: nenhum tenant e criado nem migrado para
-- esses tipos. A ativacao e decisao de produto pos-remediacao (doc 30 §7 / INV-2;
-- ex.: "Farmácia de manipulação aprovada como futuro TIPO DE TENANT").
--
-- Seguranca: a FK so AMPLIA o conjunto valido (os 3 slugs atuais + os 4 novos,
-- todos presentes em tenant_types) — nenhuma escrita existente quebra. Nenhum
-- codigo insere tenant_type fora do catalogo (verificado no Track A).
--
-- Idempotente. Down: migrations/down/049_tenant_type_referential_down.sql.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. Semear tipos FUTUROS no catalogo (apenas disponibiliza; nao ativa nada)
-- ---------------------------------------------------------------------------
INSERT INTO tenant_types (slug, label) VALUES ('pharmacy',   'Farmácia de Manipulação')  ON CONFLICT (slug) DO NOTHING;
INSERT INTO tenant_types (slug, label) VALUES ('cultivator', 'Cultivador')               ON CONFLICT (slug) DO NOTHING;
INSERT INTO tenant_types (slug, label) VALUES ('lawfirm',    'Escritório Jurídico')      ON CONFLICT (slug) DO NOTHING;
INSERT INTO tenant_types (slug, label) VALUES ('research',   'Instituição de Pesquisa')  ON CONFLICT (slug) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 2. Trocar CHECK literal (024) por validacao referencial
-- ---------------------------------------------------------------------------
-- 2a. Remove o CHECK literal restrito da 024
ALTER TABLE tenants DROP CONSTRAINT IF EXISTS chk_tenants_type;

-- 2b. Adiciona FK referencial (tenant_types.slug e UNIQUE — migration 004).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_tenants_type_slug'
    ) THEN
        ALTER TABLE tenants
          ADD CONSTRAINT fk_tenants_type_slug
          FOREIGN KEY (tenant_type) REFERENCES tenant_types(slug);
    END IF;
END
$$;
