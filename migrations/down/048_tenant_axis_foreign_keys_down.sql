-- Down de 048_tenant_axis_foreign_keys.sql
--
-- Remove as 3 FKs do eixo tenant. Reversao NAO-destrutiva: nao toca dados,
-- apenas dropa as constraints (a limpeza de orfaos da UP nao e revertida —
-- orfaos apagados nao voltam, o que e o comportamento correto).
--
-- Apos rodar este down, lembre de:
--   DELETE FROM schema_migrations WHERE version = '048';
-- (ver migrations/down/README.md)

ALTER TABLE clinics            DROP CONSTRAINT IF EXISTS fk_clinics_tenant_id;
ALTER TABLE user_tenant_roles  DROP CONSTRAINT IF EXISTS fk_user_tenant_roles_user;
ALTER TABLE user_tenant_roles  DROP CONSTRAINT IF EXISTS fk_user_tenant_roles_tenant;
