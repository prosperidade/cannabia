-- Migration 017: Knowledge source monitors
-- URLs that the extractor agent watches for new content

CREATE TABLE IF NOT EXISTS knowledge_monitors (
    id              SERIAL PRIMARY KEY,
    clinic_id       INT DEFAULT 1,

    -- Source definition
    name            VARCHAR(255) NOT NULL,
    url             TEXT NOT NULL,
    source_type     VARCHAR(50) NOT NULL,  -- 'rss', 'html_page', 'pubmed_query', 'anvisa', 'dou'

    -- Search config
    search_query    TEXT,                  -- For PubMed: search terms. For HTML: CSS selector
    check_interval_hours INT DEFAULT 24,  -- How often to check
    max_items       INT DEFAULT 10,       -- Max items per check

    -- State
    is_active       BOOLEAN DEFAULT TRUE,
    last_checked_at TIMESTAMPTZ,
    last_hash       VARCHAR(64),          -- Hash of last seen content (detect changes)
    items_found     INT DEFAULT 0,        -- Total items found historically

    -- Metadata
    created_by      INT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_monitors_active ON knowledge_monitors (is_active, last_checked_at);

-- Seed default monitors for cannabis medicinal
INSERT INTO knowledge_monitors (name, url, source_type, search_query, check_interval_hours)
VALUES
    ('PubMed - CBD Therapeutic', 'https://pubmed.ncbi.nlm.nih.gov/', 'pubmed_query', 'cannabidiol therapeutic systematic review', 24),
    ('PubMed - Cannabis Pain', 'https://pubmed.ncbi.nlm.nih.gov/', 'pubmed_query', 'medical cannabis chronic pain clinical trial', 24),
    ('PubMed - CBD Epilepsy', 'https://pubmed.ncbi.nlm.nih.gov/', 'pubmed_query', 'cannabidiol epilepsy treatment', 48),
    ('PubMed - THC Safety', 'https://pubmed.ncbi.nlm.nih.gov/', 'pubmed_query', 'THC safety pharmacokinetics dosage', 48),
    ('PubMed - Cannabis Anxiety', 'https://pubmed.ncbi.nlm.nih.gov/', 'pubmed_query', 'cannabis anxiety disorder randomized', 48),
    ('ANVISA - Cannabis Portal', 'https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/cannabis', 'html_page', NULL, 72),
    ('DOU - Resolucoes ANVISA', 'https://www.in.gov.br/consulta', 'html_page', 'anvisa cannabis', 24),
    ('Planalto - Lei de Drogas', 'https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11343.htm', 'html_page', NULL, 168)
ON CONFLICT DO NOTHING;
