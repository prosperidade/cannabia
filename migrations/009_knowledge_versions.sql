-- 009_knowledge_versions.sql
-- Versionamento da base de conhecimento RAG (Fase 3.4)
--
-- Arquitetura:
--   knowledge_base_versions — controle de versões da KB (apenas 1 ativa por tenant)
--   knowledge_documents     — rastreamento de cada documento ingerido + metadados
--
-- Regra: queries RAG usam apenas documentos da versão ativa.
-- Versionamento permite rollback e A/B testing de bases de conhecimento.

BEGIN;

-- ─── Tabela de versões da KB ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_base_versions (
    id              SERIAL PRIMARY KEY,
    clinic_id       INTEGER NOT NULL,
    version_label   VARCHAR(50) NOT NULL,          -- ex: "v1.0", "v2.1-oncology"
    description     TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT FALSE,
    document_count  INTEGER NOT NULL DEFAULT 0,
    total_chunks    INTEGER NOT NULL DEFAULT 0,
    created_by      VARCHAR(100),                  -- user_id de quem criou
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at    TIMESTAMPTZ,                   -- quando foi marcada como ativa
    deactivated_at  TIMESTAMPTZ,

    -- Apenas 1 versão ativa por tenant (partial unique index)
    CONSTRAINT uq_kb_version_label_per_clinic UNIQUE (clinic_id, version_label)
);

-- Índice parcial: garante no máximo 1 versão ativa por clinic_id
CREATE UNIQUE INDEX IF NOT EXISTS idx_kb_one_active_per_clinic
    ON knowledge_base_versions (clinic_id)
    WHERE is_active = TRUE;

-- ─── Tabela de documentos ingeridos ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id              SERIAL PRIMARY KEY,
    version_id      INTEGER NOT NULL REFERENCES knowledge_base_versions(id) ON DELETE CASCADE,
    clinic_id       INTEGER NOT NULL,
    filename        VARCHAR(500) NOT NULL,
    file_hash       VARCHAR(64) NOT NULL,          -- SHA-256 do arquivo original
    file_size_bytes INTEGER,
    mime_type       VARCHAR(100),
    chunk_count     INTEGER NOT NULL DEFAULT 0,
    metadata        JSONB DEFAULT '{}'::JSONB,     -- título, DOI, autores, etc.
    ingested_by     VARCHAR(100),                  -- user_id de quem fez upload
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message   TEXT,

    -- Impede reingestion do mesmo arquivo na mesma versão
    CONSTRAINT uq_doc_hash_per_version UNIQUE (version_id, file_hash)
);

CREATE INDEX IF NOT EXISTS idx_kb_docs_version ON knowledge_documents(version_id);
CREATE INDEX IF NOT EXISTS idx_kb_docs_clinic  ON knowledge_documents(clinic_id);
CREATE INDEX IF NOT EXISTS idx_kb_docs_status  ON knowledge_documents(status);

COMMIT;
