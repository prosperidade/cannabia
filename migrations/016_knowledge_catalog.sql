-- Migration 016: Unified Knowledge Catalog
-- Central registry for all knowledge sources (articles, legislation, guidelines)
-- Documents can be stored in ChromaDB (chunks) or Google Files API (full) or both

CREATE TABLE IF NOT EXISTS knowledge_catalog (
    id              SERIAL PRIMARY KEY,
    clinic_id       INT DEFAULT 1,

    -- Document identity
    title           VARCHAR(500) NOT NULL,
    doc_type        VARCHAR(50) NOT NULL,  -- 'article', 'legislation', 'guideline', 'protocol', 'bula'
    source          VARCHAR(50) NOT NULL,  -- 'pubmed', 'scholar', 'anvisa', 'planalto', 'cfm', 'manual_upload', 'crossref'
    source_url      TEXT,
    doi             VARCHAR(100),

    -- Classification
    category        VARCHAR(100),           -- 'cannabis_medicinal', 'epilepsia', 'dor_cronica', etc
    subcategory     VARCHAR(100),
    tags            JSONB DEFAULT '[]'::jsonb,

    -- Content metadata
    authors         JSONB DEFAULT '[]'::jsonb,  -- ["Author 1", "Author 2"]
    journal         VARCHAR(255),
    published_date  DATE,
    language        VARCHAR(10) DEFAULT 'pt-BR',
    abstract        TEXT,

    -- For legislation
    norm_number     VARCHAR(100),           -- 'RDC 327/2019', 'Lei 11.343/2006'
    norm_body       VARCHAR(100),           -- 'ANVISA', 'CFM', 'Congresso Nacional'
    norm_status     VARCHAR(50),            -- 'vigente', 'revogada', 'alterada'

    -- Storage routing
    storage_type    VARCHAR(50) NOT NULL DEFAULT 'pending',  -- 'chromadb', 'google_files', 'both', 'pending'
    chromadb_chunks INT DEFAULT 0,          -- Number of chunks in ChromaDB
    google_file_uri TEXT,                   -- Google Files API URI
    google_file_name VARCHAR(255),          -- Google Files API file name
    local_path      TEXT,                   -- Local filesystem path (if downloaded)
    file_hash       VARCHAR(64),            -- SHA-256 of the original file
    file_size_bytes INT DEFAULT 0,
    mime_type       VARCHAR(100) DEFAULT 'application/pdf',

    -- Processing status
    status          VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'downloading', 'processing', 'indexed', 'failed', 'archived'
    error_message   TEXT,

    -- Metadata
    ingested_by     VARCHAR(100) DEFAULT 'system',  -- 'agent_extrator', 'manual_upload', 'auto_search'
    ingested_at     TIMESTAMPTZ DEFAULT NOW(),
    last_checked_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_knowledge_catalog_type ON knowledge_catalog (doc_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_catalog_source ON knowledge_catalog (source);
CREATE INDEX IF NOT EXISTS idx_knowledge_catalog_status ON knowledge_catalog (status);
CREATE INDEX IF NOT EXISTS idx_knowledge_catalog_category ON knowledge_catalog (category);
CREATE INDEX IF NOT EXISTS idx_knowledge_catalog_clinic ON knowledge_catalog (clinic_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_catalog_doi ON knowledge_catalog (doi) WHERE doi IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_knowledge_catalog_norm ON knowledge_catalog (norm_number) WHERE norm_number IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_catalog_unique_doi ON knowledge_catalog (doi) WHERE doi IS NOT NULL AND doi != '';
CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_catalog_unique_url ON knowledge_catalog (source_url) WHERE source_url IS NOT NULL AND source_url != '';
