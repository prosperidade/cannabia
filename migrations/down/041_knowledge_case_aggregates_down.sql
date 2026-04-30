-- Rollback da migration 041.
BEGIN;

DROP INDEX IF EXISTS idx_knowledge_catalog_doc_type_case_aggregate;
DROP INDEX IF EXISTS idx_knowledge_catalog_case_aggregate_metadata;
ALTER TABLE knowledge_catalog DROP COLUMN IF EXISTS case_aggregate_metadata;

COMMIT;
