-- Migration 025: Governance Schema (F1.2 do docs/BACKLOG_SCC.md)
--
-- Cria as quatro tabelas do dominio `governance` previstas no
-- docs/25_SCC_DATA_MODEL_AND_MIGRATIONS.md secoes 4.2 a 4.5:
--
--   4.4  institutional_documents       — documentos institucionais por tenant
--   4.3  technical_responsibles        — responsaveis tecnicos (medicos/farmac.)
--   4.2  associations                  — extensao 1:1 de tenants do tipo association
--   4.5  technical_operational_capacity— snapshot de maturidade operacional
--
-- Ordem de criacao respeita a unica FK interna desta migration:
--   associations.statute_document_id -> institutional_documents.id
-- Por isso `institutional_documents` e criada ANTES de `associations`.
--
-- Dependencias externas (criadas em migrations anteriores):
--   - tenants(id)           — evoluida em 024_tenants_evolution
--   - users(id)             — foundation (001+)
--
-- Decisao de namespace: seguimos o padrao do repo (schema `public`), ja que
-- 022/023/024 nao usam schemas separados. Doc 25 §3 permite essa escolha.
--
-- Idempotencia: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.
-- CHECKs e UNIQUE sao inline no CREATE TABLE (nao re-executam em re-runs
-- porque o CREATE TABLE e skipado). Se alguem dropar constraints manualmente,
-- o caminho correto e rodar o down-script e reaplicar a up.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- 1. institutional_documents  (doc 25 §4.4)
--
-- Documentos institucionais com rastreabilidade por hash (file_hash CHAR(64)
-- = SHA-256 hex) e janela de validade (valid_from / valid_until). Criada
-- primeiro porque `associations.statute_document_id` aponta para aqui.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS institutional_documents (
    id             SERIAL PRIMARY KEY,
    tenant_id      INT NOT NULL REFERENCES tenants(id),
    document_type  VARCHAR(64) NOT NULL,
    title          VARCHAR(255) NOT NULL,
    version        VARCHAR(32) NOT NULL,
    file_uri       TEXT NOT NULL,
    file_hash      CHAR(64) NOT NULL,
    valid_from     DATE NOT NULL,
    valid_until    DATE,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    uploaded_by    INT REFERENCES users(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inst_docs_tenant
    ON institutional_documents (tenant_id);
CREATE INDEX IF NOT EXISTS idx_inst_docs_type
    ON institutional_documents (document_type);


-- ---------------------------------------------------------------------------
-- 2. technical_responsibles  (doc 25 §4.3)
--
-- O UNIQUE (professional_council, council_number, council_state) reflete a
-- realidade regulatoria brasileira: um profissional e unico por conselho +
-- estado + numero. NAO inclui tenant_id de proposito — o mesmo RT nao pode
-- estar cadastrado em dois tenants simultaneamente com a mesma matricula.
--
-- `document_ids INT[]` nao cria FK real (Postgres nao suporta FK em arrays);
-- e apenas metadado de quais institutional_documents estao anexados. A
-- integridade fica a cargo da camada de servico.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS technical_responsibles (
    id                       SERIAL PRIMARY KEY,
    tenant_id                INT NOT NULL REFERENCES tenants(id),
    user_id                  INT REFERENCES users(id),
    full_name                VARCHAR(255) NOT NULL,
    professional_council     VARCHAR(32) NOT NULL,
    council_number           VARCHAR(32) NOT NULL,
    council_state            VARCHAR(2) NOT NULL,
    habilitation_valid_until DATE,
    document_ids             INT[] DEFAULT '{}',
    is_active                BOOLEAN NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tr_council UNIQUE (professional_council, council_number, council_state)
);

CREATE INDEX IF NOT EXISTS idx_tr_tenant
    ON technical_responsibles (tenant_id);
CREATE INDEX IF NOT EXISTS idx_tr_active
    ON technical_responsibles (is_active);


-- ---------------------------------------------------------------------------
-- 3. associations  (doc 25 §4.2)
--
-- Extensao 1:1 para tenants do tipo 'association' (tenant_id e PK e FK ao
-- mesmo tempo). Clinicas e medicos solo nao terao linha aqui.
--
-- `sandbox_application_status` aceita NULL (associacao pode nao ter iniciado
-- aplicacao ao sandbox) e, quando presente, deve estar na whitelist do doc
-- 25 §4.2. O CHECK e escrito como `IS NULL OR IN (...)` para permitir NULL
-- explicitamente.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS associations (
    tenant_id                  INT PRIMARY KEY REFERENCES tenants(id),
    statute_document_id        INT REFERENCES institutional_documents(id),
    directive_board            JSONB NOT NULL DEFAULT '[]'::jsonb,
    members_count              INT NOT NULL DEFAULT 0,
    is_judicial_operation      BOOLEAN NOT NULL DEFAULT FALSE,
    judicial_authorization     TEXT,
    sandbox_application_status VARCHAR(32),
    eligibility_validated_at   TIMESTAMPTZ,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_assoc_sandbox_status CHECK (
        sandbox_application_status IS NULL
        OR sandbox_application_status IN (
            'not_started', 'preparing', 'submitted',
            'approved', 'active', 'concluded', 'discontinued'
        )
    ),
    CONSTRAINT chk_assoc_members_count CHECK (members_count >= 0)
);


-- ---------------------------------------------------------------------------
-- 4. technical_operational_capacity  (doc 25 §4.5)
--
-- Snapshot imutavel por data de avaliacao. Os quatro scores JSONB sao NOT
-- NULL porque o doc exige avaliacao completa — avaliacao parcial nao conta.
-- `overall_readiness` e nullable (pode ser calculado depois a partir dos
-- scores).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS technical_operational_capacity (
    id                     SERIAL PRIMARY KEY,
    tenant_id              INT NOT NULL REFERENCES tenants(id),
    assessment_date        DATE NOT NULL,
    infrastructure_score   JSONB NOT NULL,
    human_resources_score  JSONB NOT NULL,
    process_maturity_score JSONB NOT NULL,
    proposed_scale         JSONB NOT NULL,
    overall_readiness      NUMERIC(5,2),
    assessed_by            INT REFERENCES users(id),
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_toc_readiness CHECK (
        overall_readiness IS NULL
        OR (overall_readiness >= 0 AND overall_readiness <= 100)
    )
);


-- ============================================================================
-- Fim da migration 025. O runner registra versao e checksum em
-- schema_migrations; nao e necessario INSERT manual aqui.
-- ============================================================================
