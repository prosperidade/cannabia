-- Down migration 040: reverte a base de conhecimento global + autoria.
-- Restaura `clinic_id INT DEFAULT 1` e remove `created_by` em
-- knowledge_catalog e knowledge_monitors.

BEGIN;

ALTER TABLE knowledge_monitors
    DROP CONSTRAINT IF EXISTS fk_knowledge_monitors_created_by;

DROP INDEX IF EXISTS idx_knowledge_monitors_created_by;

ALTER TABLE knowledge_monitors
    DROP COLUMN IF EXISTS created_by;

ALTER TABLE knowledge_monitors
    ADD COLUMN IF NOT EXISTS clinic_id INT DEFAULT 1;


ALTER TABLE knowledge_catalog
    DROP CONSTRAINT IF EXISTS fk_knowledge_catalog_created_by;

DROP INDEX IF EXISTS idx_knowledge_catalog_created_by;

ALTER TABLE knowledge_catalog
    DROP COLUMN IF EXISTS created_by;

ALTER TABLE knowledge_catalog
    ADD COLUMN IF NOT EXISTS clinic_id INT DEFAULT 1;

COMMIT;
