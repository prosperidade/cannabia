-- Down migration 028: reverter Traceability Schema Base
--
-- Reverte a criacao das 9 tabelas do dominio `traceability` base aplicadas
-- pela up-migration 028_traceability_schema_base.sql.
--
-- ATENCAO — perda informacional:
--
-- Dropar estas tabelas destroi toda a cadeia de rastreabilidade registrada
-- (matrizes, sementes, cultivos, plantas, colheitas, extracoes, preparados,
-- laudos, dispensacoes). Em ambiente sandbox isso quebra evidencia
-- regulatoria — o caminho oficial para voltar a um estado anterior com
-- dados e restore por backup, ver docs/BACKUP_AND_DISASTER_RECOVERY.md §4.
--
-- PostGIS extension NAO e dropada pelo down — pode ser requerida por
-- migrations futuras (traceability_events em 029) ou outros ambientes
-- que a usem para outras features.
--
-- Ordem de drop e INVERSA a ordem de criacao, respeitando FKs:
--
--   dispensations        → preparations, association_members, prescriptions
--   lab_analyses         → (polimorfica, sem FK nativa)
--   preparations         → extractions
--   extractions          → harvests
--   harvests             → cultivation_batches
--   plants               → cultivation_batches
--   cultivation_batches  → seed_lots, genetic_matrices
--   seed_lots            → genetic_matrices
--   genetic_matrices     → (sem deps)
--
-- Idempotente: todos os DROPs usam IF EXISTS.
-- ============================================================================

DROP TABLE IF EXISTS dispensations;
DROP TABLE IF EXISTS lab_analyses;
DROP TABLE IF EXISTS preparations;
DROP TABLE IF EXISTS extractions;
DROP TABLE IF EXISTS harvests;
DROP TABLE IF EXISTS plants;
DROP TABLE IF EXISTS cultivation_batches;
DROP TABLE IF EXISTS seed_lots;
DROP TABLE IF EXISTS genetic_matrices;


-- ============================================================================
-- Fim do down 028. Apos executar, remova manualmente o registro:
--   DELETE FROM schema_migrations WHERE version = '028';
-- ============================================================================
