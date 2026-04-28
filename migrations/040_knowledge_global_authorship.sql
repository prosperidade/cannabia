-- Migration 040: Base de conhecimento explicitamente global + autoria.
--
-- Decisoes (P1 do progresso25):
--   1. A base de conhecimento (knowledge_catalog + knowledge_monitors) e
--      explicitamente GLOBAL — nao escopada por tenant. Todos os
--      tenants credenciados (Admin global, AdminClinica, Medico) leem
--      e adicionam num pool compartilhado. So Admin global e o autor
--      original podem deletar.
--
--   2. Removemos a coluna `clinic_id` que existia em ambas as tabelas
--      como `INT DEFAULT 1` mas nunca foi filtrada em nenhuma query —
--      ou seja, era um campo morto que dava falsa impressao de
--      multi-tenant. A remocao deixa explicito que o pool e global.
--
--   3. Adicionamos `created_by INT REFERENCES users(id)` para
--      rastrear autoria (quem adicionou cada documento ou monitor).
--      Necessario para a regra de DELETE em knowledge.py:
--         - Admin global: pode deletar qualquer item
--         - AdminClinica: so pode deletar o que ela mesma adicionou
--
-- Idempotente: usa IF EXISTS / IF NOT EXISTS.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. knowledge_catalog
-- ---------------------------------------------------------------------------

ALTER TABLE knowledge_catalog
    ADD COLUMN IF NOT EXISTS created_by INT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_knowledge_catalog_created_by'
          AND table_name = 'knowledge_catalog'
    ) THEN
        ALTER TABLE knowledge_catalog
            ADD CONSTRAINT fk_knowledge_catalog_created_by
            FOREIGN KEY (created_by) REFERENCES users(id);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_knowledge_catalog_created_by
    ON knowledge_catalog (created_by);

ALTER TABLE knowledge_catalog
    DROP COLUMN IF EXISTS clinic_id;


-- ---------------------------------------------------------------------------
-- 2. knowledge_monitors
-- ---------------------------------------------------------------------------

ALTER TABLE knowledge_monitors
    ADD COLUMN IF NOT EXISTS created_by INT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_knowledge_monitors_created_by'
          AND table_name = 'knowledge_monitors'
    ) THEN
        ALTER TABLE knowledge_monitors
            ADD CONSTRAINT fk_knowledge_monitors_created_by
            FOREIGN KEY (created_by) REFERENCES users(id);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_knowledge_monitors_created_by
    ON knowledge_monitors (created_by);

ALTER TABLE knowledge_monitors
    DROP COLUMN IF EXISTS clinic_id;

COMMIT;
