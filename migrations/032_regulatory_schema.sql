-- Migration 032: Regulatory Schema (F3.2 do docs/BACKLOG_SCC.md)
--
-- Cria as 6 tabelas do dominio `regulatory` previstas no
-- docs/25_SCC_DATA_MODEL_AND_MIGRATIONS.md secoes 9.1 a 9.3:
--
--   9.1  sandbox_projects + sandbox_protocols
--   9.2  sandbox_indicators + sandbox_indicator_values
--   9.3  regulatory_submissions + regulatory_reports
--
-- Ordem de criacao respeita FKs internas:
--   sandbox_projects → sandbox_protocols
--                   → sandbox_indicators → sandbox_indicator_values
--                   → regulatory_submissions
--                   → regulatory_reports
--
-- Dependencias externas (ja criadas):
--   - tenants(id)  — 024
--   - users(id)    — foundation
--
-- sandbox_indicator_values e BIGSERIAL — alta frequencia de insercao
-- (indicadores diarios/semanais de projetos sandbox de longa duracao).
--
-- Idempotencia: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- 1. sandbox_projects  (doc 25 §9.1)
--
-- Timeline do projeto: draft → submitted → under_review → approved → active
-- → (suspended | concluded | discontinued). Timestamps correspondentes sao
-- NULLABLE para estados anteriores.
--
-- CHECKs defensivos de ordem temporal:
--   approved_at >= submitted_at
--   started_at  >= approved_at
--   concluded_at >= started_at
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sandbox_projects (
    id               SERIAL PRIMARY KEY,
    tenant_id        INT NOT NULL REFERENCES tenants(id),
    project_code     VARCHAR(64) NOT NULL,
    title            VARCHAR(255) NOT NULL,
    status           VARCHAR(32) NOT NULL,
    submitted_at     TIMESTAMPTZ,
    approved_at      TIMESTAMPTZ,
    started_at       TIMESTAMPTZ,
    concluded_at     TIMESTAMPTZ,
    anvisa_reference VARCHAR(128),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sandbox_projects_tenant_code UNIQUE (tenant_id, project_code),
    CONSTRAINT chk_sandbox_projects_status CHECK (
        status IN ('draft', 'submitted', 'under_review', 'approved',
                   'active', 'suspended', 'concluded', 'discontinued')
    ),
    CONSTRAINT chk_sandbox_projects_approved_order CHECK (
        submitted_at IS NULL OR approved_at IS NULL OR approved_at >= submitted_at
    ),
    CONSTRAINT chk_sandbox_projects_started_order CHECK (
        approved_at IS NULL OR started_at IS NULL OR started_at >= approved_at
    ),
    CONSTRAINT chk_sandbox_projects_concluded_order CHECK (
        started_at IS NULL OR concluded_at IS NULL OR concluded_at >= started_at
    )
);

CREATE INDEX IF NOT EXISTS idx_sandbox_projects_tenant ON sandbox_projects (tenant_id);
CREATE INDEX IF NOT EXISTS idx_sandbox_projects_status ON sandbox_projects (status);


-- ---------------------------------------------------------------------------
-- 2. sandbox_protocols  (doc 25 §9.1)
--
-- Protocolo versionado por projeto: JSONBs guardam escopo, normas,
-- parametros, planos de contingencia e obrigacoes de data sharing. Cada
-- modificacao gera uma nova versao — modelo append-style (embora sem
-- trigger append-only; versoes antigas permanecem com effective_until
-- setado e nova linha assume vigencia).
--
-- CHECK defensivo: effective_until >= effective_from.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sandbox_protocols (
    id                       SERIAL PRIMARY KEY,
    project_id               INT NOT NULL REFERENCES sandbox_projects(id),
    protocol_version         VARCHAR(32) NOT NULL,
    scope                    JSONB NOT NULL,
    applicable_norms         JSONB NOT NULL,
    modulated_norms          JSONB NOT NULL DEFAULT '{}'::jsonb,
    monitoring_parameters    JSONB NOT NULL,
    discontinuity_plan       JSONB NOT NULL,
    quality_requirements     JSONB NOT NULL,
    data_sharing_obligations JSONB NOT NULL,
    effective_from           TIMESTAMPTZ,
    effective_until          TIMESTAMPTZ,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sandbox_protocols_version UNIQUE (project_id, protocol_version),
    CONSTRAINT chk_sandbox_protocols_effective_order CHECK (
        effective_from IS NULL
        OR effective_until IS NULL
        OR effective_until >= effective_from
    )
);

CREATE INDEX IF NOT EXISTS idx_sandbox_protocols_project ON sandbox_protocols (project_id);


-- ---------------------------------------------------------------------------
-- 3. sandbox_indicators  (doc 25 §9.2)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sandbox_indicators (
    id                  SERIAL PRIMARY KEY,
    project_id          INT NOT NULL REFERENCES sandbox_projects(id),
    indicator_code      VARCHAR(64) NOT NULL,
    indicator_name      VARCHAR(255) NOT NULL,
    calculation_formula TEXT NOT NULL,
    unit                VARCHAR(32),
    target_value        NUMERIC(18,4),
    reporting_frequency VARCHAR(32) NOT NULL,
    is_mandatory        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sandbox_indicators_code UNIQUE (project_id, indicator_code),
    CONSTRAINT chk_sandbox_indicators_frequency CHECK (
        reporting_frequency IN ('daily', 'weekly', 'monthly', 'quarterly', 'annual')
    )
);

CREATE INDEX IF NOT EXISTS idx_sandbox_indicators_project ON sandbox_indicators (project_id);


-- ---------------------------------------------------------------------------
-- 4. sandbox_indicator_values  (doc 25 §9.2)
--
-- BIGSERIAL porque projetos sandbox de 24-60 meses acumulam muitos valores
-- (indicadores diarios x anos).
--
-- CHECK defensivo: period_end >= period_start.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sandbox_indicator_values (
    id                  BIGSERIAL PRIMARY KEY,
    indicator_id        INT NOT NULL REFERENCES sandbox_indicators(id),
    period_start        TIMESTAMPTZ NOT NULL,
    period_end          TIMESTAMPTZ NOT NULL,
    calculated_value    NUMERIC(18,4) NOT NULL,
    calculation_details JSONB,
    calculated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_siv_period_order CHECK (period_end >= period_start)
);

CREATE INDEX IF NOT EXISTS idx_siv_indicator ON sandbox_indicator_values (indicator_id);
CREATE INDEX IF NOT EXISTS idx_siv_period
    ON sandbox_indicator_values (period_start, period_end);


-- ---------------------------------------------------------------------------
-- 5. regulatory_submissions  (doc 25 §9.3)
--
-- `payload_hash` CHAR(64) = SHA-256 em hex. Immutable evidencia da
-- submissao original, independente do storage do `payload_uri`.
-- project_id e opcional (pode haver submissoes globais do tenant, nao
-- ligadas a um projeto especifico).
--
-- CHECK defensivo: anvisa_response_at >= submitted_at.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS regulatory_submissions (
    id                  SERIAL PRIMARY KEY,
    tenant_id           INT NOT NULL REFERENCES tenants(id),
    project_id          INT REFERENCES sandbox_projects(id),
    submission_type     VARCHAR(64) NOT NULL,
    submitted_at        TIMESTAMPTZ NOT NULL,
    submitted_by        INT REFERENCES users(id),
    payload_uri         TEXT NOT NULL,
    payload_hash        CHAR(64) NOT NULL,
    anvisa_response_uri TEXT,
    anvisa_response_at  TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_reg_submissions_response_order CHECK (
        anvisa_response_at IS NULL OR anvisa_response_at >= submitted_at
    )
);

CREATE INDEX IF NOT EXISTS idx_reg_submissions_tenant ON regulatory_submissions (tenant_id);
CREATE INDEX IF NOT EXISTS idx_reg_submissions_project ON regulatory_submissions (project_id);


-- ---------------------------------------------------------------------------
-- 6. regulatory_reports  (doc 25 §9.3)
--
-- 7 tipos de relatorio regulatorio conforme whitelist do doc 25 §9.3.
-- `content_hash` SHA-256 da versao aprovada — comparado com recalculo do
-- arquivo para detectar adulteracao.
--
-- CHECK defensivo: approved_at >= generated_at.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS regulatory_reports (
    id           SERIAL PRIMARY KEY,
    tenant_id    INT NOT NULL REFERENCES tenants(id),
    project_id   INT REFERENCES sandbox_projects(id),
    report_type  VARCHAR(64) NOT NULL,
    version      VARCHAR(32) NOT NULL,
    content_uri  TEXT NOT NULL,
    content_hash CHAR(64) NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_by  INT REFERENCES users(id),
    approved_at  TIMESTAMPTZ,
    CONSTRAINT chk_reg_reports_type CHECK (
        report_type IN (
            'work_plan', 'communication_plan', 'discontinuity_plan',
            'monitoring_plan', 'risk_management_plan',
            'final_monitoring_opinion', 'eligibility_dossier'
        )
    ),
    CONSTRAINT chk_reg_reports_approval_order CHECK (
        approved_at IS NULL OR approved_at >= generated_at
    )
);

CREATE INDEX IF NOT EXISTS idx_reg_reports_tenant ON regulatory_reports (tenant_id);
CREATE INDEX IF NOT EXISTS idx_reg_reports_type ON regulatory_reports (report_type);


-- ============================================================================
-- Fim da migration 032.
-- ============================================================================
