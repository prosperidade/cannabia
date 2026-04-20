-- Down migration 029: reverter Traceability Events
--
-- Reverte a criacao da tabela `traceability_events` aplicada pela up.
--
-- ATENCAO — perda informacional:
--
-- Dropar traceability_events destroi TODOS os eventos de rastreabilidade
-- imutaveis. Em ambiente sandbox isso quebra evidencia regulatoria em
-- niveis irrecuperaveis — o caminho oficial para voltar a um estado
-- anterior com dados e restore por backup, ver
-- docs/BACKUP_AND_DISASTER_RECOVERY.md §4.
--
-- Se 030 ja foi aplicada (triggers em traceability_events), o down dela
-- precisa rodar ANTES desta. O down de 030 dropa os triggers; aqui
-- assumimos que a tabela esta "limpa" (sem triggers ativos).
--
-- Idempotente: DROP TABLE IF EXISTS.
-- ============================================================================

DROP TABLE IF EXISTS traceability_events;


-- ============================================================================
-- Fim do down 029. Apos executar, remova manualmente o registro:
--   DELETE FROM schema_migrations WHERE version = '029';
-- ============================================================================
