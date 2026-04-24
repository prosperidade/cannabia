-- Down migration 037: dropa as funcoes de seed.
--
-- ATENCAO: NAO remove dados ja seedados. Linhas em sanitary_risks e
-- sops criadas via seed_sandbox_defaults permanecem — fica a cargo do
-- operador limpar manualmente se desejar:
--
--   DELETE FROM sanitary_risks WHERE risk_code LIKE 'RISK-%-001'
--                                 OR risk_code LIKE 'RISK-%-002';
--   DELETE FROM sops WHERE code LIKE 'SOP-%-001' OR code LIKE 'SOP-%-002';
--
-- Esses DELETEs nao estao automatizados aqui porque os codes podem ter
-- sido editados pelo tenant (atualizar versao, corrigir descricao) e
-- excluir indiscriminadamente perderia trabalho real.
--
-- Idempotente: DROP FUNCTION IF EXISTS.
-- ============================================================================

DROP FUNCTION IF EXISTS seed_sandbox_defaults_all_associations();
DROP FUNCTION IF EXISTS seed_sandbox_defaults(INT);


-- ============================================================================
-- Fim do down 037. Apos executar, remova manualmente o registro:
--   DELETE FROM schema_migrations WHERE version = '037';
-- ============================================================================
