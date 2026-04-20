-- Down migration 025: reverter Governance Schema
--
-- Reverte a criacao das quatro tabelas do dominio `governance` aplicadas
-- pela up-migration 025_governance_schema.sql.
--
-- ATENCAO — perda informacional:
--
-- Dropar `institutional_documents`, `technical_responsibles`, `associations`
-- e `technical_operational_capacity` **descarta** todos os registros
-- armazenados (documentos, responsaveis tecnicos, metadados de associacoes
-- e snapshots de capacidade operacional). O caminho oficial para voltar a
-- um estado anterior com dados e restore por backup — ver
-- docs/BACKUP_AND_DISASTER_RECOVERY.md §4.
--
-- `tenants` e `users` nao sao tocadas aqui (existiam antes da 025).
--
-- Ordem de drop e INVERSA a ordem de criacao, por causa da FK interna
-- `associations.statute_document_id -> institutional_documents.id`:
--
--   associations                     (dependente)
--   technical_operational_capacity   (independente, sem filhas)
--   technical_responsibles           (independente, sem filhas)
--   institutional_documents          (referenciada por associations)
--
-- Idempotente: todos os DROPs usam IF EXISTS.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Tabelas (em ordem reversa da criacao)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS associations;
DROP TABLE IF EXISTS technical_operational_capacity;
DROP TABLE IF EXISTS technical_responsibles;
DROP TABLE IF EXISTS institutional_documents;


-- ============================================================================
-- Fim do down 025. Apos executar, remova manualmente o registro:
--   DELETE FROM schema_migrations WHERE version = '025';
--
-- Indexes, CHECKs e UNIQUE sao dropados em cascata junto com as tabelas.
-- Sequences (SERIAL) sao dropadas automaticamente via OWNED BY.
-- ============================================================================
