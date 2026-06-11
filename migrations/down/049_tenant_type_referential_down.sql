-- Down de 049_tenant_type_referential.sql
--
-- Reverte para o CHECK literal da 024 e remove os tipos futuros semeados.
-- Pre-condicao: nenhum tenant pode estar usando um tipo fora de
-- (clinic, association, doctor). Como a UP NAO ativa nenhum tipo novo, a
-- reversao e segura enquanto a ativacao nao tiver ocorrido (a guarda do
-- passo 3 protege contra remover tipos em uso).
--
-- Apos rodar: DELETE FROM schema_migrations WHERE version = '049';

-- 1. Remove a FK referencial
ALTER TABLE tenants DROP CONSTRAINT IF EXISTS fk_tenants_type_slug;

-- 2. Re-adiciona o CHECK literal da 024 (idempotente)
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

-- 3. Remove os tipos futuros do catalogo — SOMENTE se nao referenciados
DELETE FROM tenant_types
 WHERE slug IN ('pharmacy', 'cultivator', 'lawfirm', 'research')
   AND id   NOT IN (SELECT tenant_type_id FROM tenants WHERE tenant_type_id IS NOT NULL)
   AND slug NOT IN (SELECT tenant_type    FROM tenants);
