-- Down migration 033: reverter Crypto Schema
--
-- Reverte a criacao das 2 tabelas do dominio crypto (doc 25 §§10.1-10.2).
--
-- ATENCAO — perda informacional:
--
-- Dropar blockchain_anchors destroi os registros de ancoragem publica que
-- sao a PROVA de imutabilidade da plataforma. As txids e proof_uris
-- permanecem recuperaveis nas redes publicas (Bitcoin OTS / Polygon /
-- Ethereum), mas a ligacao local eventos → anchor em anchor_event_mappings
-- tambem e perdida. Em ambiente com dados reais, o caminho oficial e
-- restore por backup — ver docs/BACKUP_AND_DISASTER_RECOVERY.md §4.
--
-- Ordem de drop e INVERSA a ordem de criacao, respeitando FKs:
--
--   anchor_event_mappings → blockchain_anchors
--   blockchain_anchors    → (raiz do dominio)
--
-- Idempotente: DROP TABLE IF EXISTS.
-- ============================================================================

DROP TABLE IF EXISTS anchor_event_mappings;
DROP TABLE IF EXISTS blockchain_anchors;


-- ============================================================================
-- Fim do down 033. Apos executar, remova manualmente o registro:
--   DELETE FROM schema_migrations WHERE version = '033';
-- ============================================================================
