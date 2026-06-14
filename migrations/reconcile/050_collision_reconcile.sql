-- migrations/reconcile/050_collision_reconcile.sql
-- ============================================================================
-- RECONCILIAÇÃO ÚNICA da colisão de versão 050.
--
-- Causa: o Track A (#72) trouxe `050_seed_edital_monitor.sql` e o Track B/COM
-- (#73) trouxe `050_inbound_idempotency.sql` — DOIS arquivos versão 050 em main.
-- O runner (`list_migration_files`) abortava com MigrationVersionConflictError,
-- e, antes de abortar, em cada ambiente só UM dos dois 050 chegou a ser gravado
-- em `schema_migrations` (o outro foi pulado como "versão 050 já aplicada"),
-- deixando o SQL do perdedor sem rodar.
--
-- Fix de arquivo: `050_inbound_idempotency.sql` foi renomeado para
-- `055_inbound_idempotency.sql` (o seed do Track A permanece em 050, intocado).
--
-- Este reconcile fecha o gap de DADOS: rodar UMA VEZ por ambiente que aplicou
-- #72/#73 ANTES do fix, ANTES de `python -m src.infra.run_migrations`.
--   * Se a versão 050 ficou registrada como o inbound, libera o slot 050 para o
--     runner aplicar o seed (idempotente, INSERT ... WHERE NOT EXISTS) e aplicar
--     o inbound como versão 055 (idempotente, IF NOT EXISTS).
--   * Se a versão 050 já é o seed, é no-op.
-- Seguro e idempotente — rodar mais de uma vez não causa dano.
-- ============================================================================

DELETE FROM schema_migrations
WHERE version = '050'
  AND filename = '050_inbound_idempotency.sql';

-- Em seguida, rode o runner normal, que aplicará 050 (seed) e 055 (inbound):
--   python -m src.infra.run_migrations
