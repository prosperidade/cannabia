-- Migration 028: Traceability Schema Base (F2.3 do docs/BACKLOG_SCC.md)
--
-- Cria as 9 tabelas do dominio `traceability` previstas no
-- docs/25_SCC_DATA_MODEL_AND_MIGRATIONS.md secoes 7.1 a 7.5:
--
--   7.1  genetic_matrices + seed_lots
--   7.2  cultivation_batches + plants
--   7.3  harvests + extractions + preparations
--   7.4  lab_analyses
--   7.5  dispensations
--
-- Escopo EXCLUI (ficam em migrations futuras):
--   7.6  traceability_events (hash chaining) → migration 029
--   7.7  trigger append-only em traceability_events → migration 030
--   7.8  validate_chain_continuity → migration 030
--
-- Esta e a primeira migration que usa PostGIS: colunas GEOGRAPHY(POINT, 4326)
-- em cultivation_batches.geo_reference (e futuramente em traceability_events).
-- CREATE EXTENSION IF NOT EXISTS postgis habilita em ambiente novo; em
-- ambientes que ja tem a extensao, e no-op.
--
-- Ordem de criacao respeita FKs internas:
--   genetic_matrices → seed_lots → cultivation_batches → plants, harvests
--   harvests → extractions → preparations
--   preparations + association_members[026] + prescriptions[012] → dispensations
--
-- Dependencias externas (criadas em migrations anteriores):
--   - tenants(id)             — 024
--   - users(id)               — foundation
--   - prescriptions(id)       — 012
--   - association_members(id) — 026
--   - sop_versions(id)        — 027
--
-- Idempotencia: CREATE EXTENSION IF NOT EXISTS, CREATE TABLE IF NOT EXISTS,
-- CREATE INDEX IF NOT EXISTS.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 0. PostGIS extension — requerida pelas colunas GEOGRAPHY
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS postgis;


-- ---------------------------------------------------------------------------
-- 1. genetic_matrices  (doc 25 §7.1)
--
-- Matriz genetica = cultivar/strain original. qr_code e UNIQUE global
-- (nao por tenant) porque QR codes impressos em etiquetas precisam ser
-- globalmente identificaveis na cadeia de rastreabilidade.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS genetic_matrices (
    id               SERIAL PRIMARY KEY,
    tenant_id        INT NOT NULL REFERENCES tenants(id),
    matrix_code      VARCHAR(64) NOT NULL,
    strain_name      VARCHAR(128),
    origin           TEXT,
    declared_profile JSONB,
    qr_code          VARCHAR(128) UNIQUE,
    nft_reference    VARCHAR(255),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_matrices_tenant_code UNIQUE (tenant_id, matrix_code)
);

CREATE INDEX IF NOT EXISTS idx_matrices_tenant ON genetic_matrices (tenant_id);


-- ---------------------------------------------------------------------------
-- 2. seed_lots  (doc 25 §7.1)
--
-- CHECK defensivo: quantity >= 0 (lote de sementes nao pode ter quantidade
-- negativa; zero e valido para lote esgotado).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS seed_lots (
    id          SERIAL PRIMARY KEY,
    tenant_id   INT NOT NULL REFERENCES tenants(id),
    matrix_id   INT REFERENCES genetic_matrices(id),
    lot_code    VARCHAR(64) NOT NULL,
    quantity    INT NOT NULL,
    received_at DATE NOT NULL,
    supplier    VARCHAR(255),
    qr_code     VARCHAR(128) UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_seed_lots_tenant_code UNIQUE (tenant_id, lot_code),
    CONSTRAINT chk_seed_lots_quantity CHECK (quantity >= 0)
);

CREATE INDEX IF NOT EXISTS idx_seed_lots_tenant ON seed_lots (tenant_id);
CREATE INDEX IF NOT EXISTS idx_seed_lots_matrix ON seed_lots (matrix_id);


-- ---------------------------------------------------------------------------
-- 3. cultivation_batches  (doc 25 §7.2)
--
-- Primeira tabela com GEOGRAPHY: `geo_reference` guarda ponto onde o cultivo
-- ocorre (regulatorio exige para rastreabilidade geografica). SRID 4326 =
-- WGS84 (padrao global).
--
-- CHECK defensivo: ended_at >= started_at.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cultivation_batches (
    id                   SERIAL PRIMARY KEY,
    tenant_id            INT NOT NULL REFERENCES tenants(id),
    batch_code           VARCHAR(64) NOT NULL,
    source_seed_lot_id   INT REFERENCES seed_lots(id),
    source_matrix_id     INT REFERENCES genetic_matrices(id),
    started_at           DATE NOT NULL,
    ended_at             DATE,
    location_description TEXT,
    geo_reference        GEOGRAPHY(POINT, 4326),
    qr_code              VARCHAR(128) UNIQUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_batches_tenant_code UNIQUE (tenant_id, batch_code),
    CONSTRAINT chk_batches_period CHECK (
        ended_at IS NULL OR ended_at >= started_at
    )
);

CREATE INDEX IF NOT EXISTS idx_batches_tenant ON cultivation_batches (tenant_id);
CREATE INDEX IF NOT EXISTS idx_batches_seed_lot ON cultivation_batches (source_seed_lot_id);


-- ---------------------------------------------------------------------------
-- 4. plants  (doc 25 §7.2)
--
-- CHECK defensivo: removed_at >= planted_at.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plants (
    id             SERIAL PRIMARY KEY,
    tenant_id      INT NOT NULL REFERENCES tenants(id),
    batch_id       INT NOT NULL REFERENCES cultivation_batches(id),
    plant_code     VARCHAR(64) NOT NULL,
    planted_at     DATE NOT NULL,
    removed_at     DATE,
    removal_reason VARCHAR(64),
    qr_code        VARCHAR(128) UNIQUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_plants_tenant_code UNIQUE (tenant_id, plant_code),
    CONSTRAINT chk_plants_lifecycle CHECK (
        removed_at IS NULL OR removed_at >= planted_at
    )
);

CREATE INDEX IF NOT EXISTS idx_plants_tenant ON plants (tenant_id);
CREATE INDEX IF NOT EXISTS idx_plants_batch ON plants (batch_id);


-- ---------------------------------------------------------------------------
-- 5. harvests  (doc 25 §7.3)
--
-- `plant_ids INT[]` guarda quais plantas foram colhidas. Nao ha FK porque
-- Postgres nao suporta FK em arrays — integridade fica na camada de servico.
--
-- CHECKs: pesos nao-negativos (gross/net em gramas), liquido <= bruto.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS harvests (
    id             SERIAL PRIMARY KEY,
    tenant_id      INT NOT NULL REFERENCES tenants(id),
    batch_id       INT NOT NULL REFERENCES cultivation_batches(id),
    harvest_code   VARCHAR(64) NOT NULL,
    harvested_at   DATE NOT NULL,
    plant_ids      INT[] NOT NULL,
    gross_weight_g NUMERIC(12,3),
    net_weight_g   NUMERIC(12,3),
    qr_code        VARCHAR(128) UNIQUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_harvests_tenant_code UNIQUE (tenant_id, harvest_code),
    CONSTRAINT chk_harvests_weights CHECK (
        (gross_weight_g IS NULL OR gross_weight_g >= 0)
        AND (net_weight_g IS NULL OR net_weight_g >= 0)
        AND (
            gross_weight_g IS NULL
            OR net_weight_g IS NULL
            OR net_weight_g <= gross_weight_g
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_harvests_tenant ON harvests (tenant_id);
CREATE INDEX IF NOT EXISTS idx_harvests_batch ON harvests (batch_id);


-- ---------------------------------------------------------------------------
-- 6. extractions  (doc 25 §7.3)
--
-- Ligacao com sop_versions (registrada em 027): cada extracao aponta para a
-- versao de SOP vigente no momento da execucao, rastreabilidade BPF.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS extractions (
    id                 SERIAL PRIMARY KEY,
    tenant_id          INT NOT NULL REFERENCES tenants(id),
    harvest_id         INT NOT NULL REFERENCES harvests(id),
    extraction_code    VARCHAR(64) NOT NULL,
    executed_at        TIMESTAMPTZ NOT NULL,
    process_parameters JSONB NOT NULL,
    sop_version_id     INT REFERENCES sop_versions(id),
    responsible_id     INT REFERENCES users(id),
    output_weight_g    NUMERIC(12,3),
    qr_code            VARCHAR(128) UNIQUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_extractions_tenant_code UNIQUE (tenant_id, extraction_code),
    CONSTRAINT chk_extractions_output CHECK (
        output_weight_g IS NULL OR output_weight_g >= 0
    )
);

CREATE INDEX IF NOT EXISTS idx_extractions_tenant ON extractions (tenant_id);
CREATE INDEX IF NOT EXISTS idx_extractions_harvest ON extractions (harvest_id);
CREATE INDEX IF NOT EXISTS idx_extractions_sop ON extractions (sop_version_id);


-- ---------------------------------------------------------------------------
-- 7. preparations  (doc 25 §7.3)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS preparations (
    id                    SERIAL PRIMARY KEY,
    tenant_id             INT NOT NULL REFERENCES tenants(id),
    extraction_id         INT NOT NULL REFERENCES extractions(id),
    preparation_code      VARCHAR(64) NOT NULL,
    preparation_type      VARCHAR(64) NOT NULL,
    produced_at           TIMESTAMPTZ NOT NULL,
    units_produced        INT NOT NULL,
    unit_size_ml          NUMERIC(10,3),
    sop_version_id        INT REFERENCES sop_versions(id),
    warning_label_applied BOOLEAN NOT NULL DEFAULT FALSE,
    qr_code               VARCHAR(128) UNIQUE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_preparations_tenant_code UNIQUE (tenant_id, preparation_code),
    CONSTRAINT chk_preparations_units CHECK (units_produced > 0),
    CONSTRAINT chk_preparations_size CHECK (
        unit_size_ml IS NULL OR unit_size_ml > 0
    )
);

CREATE INDEX IF NOT EXISTS idx_preparations_tenant ON preparations (tenant_id);
CREATE INDEX IF NOT EXISTS idx_preparations_extraction ON preparations (extraction_id);
CREATE INDEX IF NOT EXISTS idx_preparations_sop ON preparations (sop_version_id);


-- ---------------------------------------------------------------------------
-- 8. lab_analyses  (doc 25 §7.4)
--
-- Polimorfica: subject_type + subject_id apontam para harvest, extraction ou
-- preparation. Postgres nao suporta FK polimorfico nativamente; integridade
-- e validada em camada de servico (e pelo CHECK de subject_type).
--
-- CHECKs defensivos: percentuais cannabinoides em [0, 100].
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lab_analyses (
    id                  SERIAL PRIMARY KEY,
    tenant_id           INT NOT NULL REFERENCES tenants(id),
    subject_type        VARCHAR(32) NOT NULL,
    subject_id          INT NOT NULL,
    lab_name            VARCHAR(255) NOT NULL,
    report_number       VARCHAR(128) NOT NULL,
    analysis_date       DATE NOT NULL,
    cannabinoid_profile JSONB NOT NULL,
    thc_percent         NUMERIC(6,3),
    cbd_percent         NUMERIC(6,3),
    conformity_status   VARCHAR(32) NOT NULL,
    report_uri          TEXT,
    report_hash         CHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_lab_subject_type CHECK (
        subject_type IN ('harvest', 'extraction', 'preparation')
    ),
    CONSTRAINT chk_lab_conformity CHECK (
        conformity_status IN ('conforming', 'non_conforming', 'pending')
    ),
    CONSTRAINT chk_lab_thc_range CHECK (
        thc_percent IS NULL OR (thc_percent >= 0 AND thc_percent <= 100)
    ),
    CONSTRAINT chk_lab_cbd_range CHECK (
        cbd_percent IS NULL OR (cbd_percent >= 0 AND cbd_percent <= 100)
    )
);

CREATE INDEX IF NOT EXISTS idx_lab_tenant ON lab_analyses (tenant_id);
CREATE INDEX IF NOT EXISTS idx_lab_subject ON lab_analyses (subject_type, subject_id);


-- ---------------------------------------------------------------------------
-- 9. dispensations  (doc 25 §7.5)
--
-- Ligacao com member e prescription garantem que dispensacao e rastreavel
-- ate o paciente final. warning_acknowledged documenta que o paciente
-- recebeu a informacao sobre advertencias (LGPD + regulatorio).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dispensations (
    id                   SERIAL PRIMARY KEY,
    tenant_id            INT NOT NULL REFERENCES tenants(id),
    preparation_id       INT NOT NULL REFERENCES preparations(id),
    member_id            INT NOT NULL REFERENCES association_members(id),
    prescription_id      INT NOT NULL REFERENCES prescriptions(id),
    units_dispensed      INT NOT NULL,
    dispensed_at         TIMESTAMPTZ NOT NULL,
    dispensed_by         INT REFERENCES users(id),
    warning_acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    qr_code              VARCHAR(128) UNIQUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_dispensations_units CHECK (units_dispensed > 0)
);

CREATE INDEX IF NOT EXISTS idx_disp_tenant ON dispensations (tenant_id);
CREATE INDEX IF NOT EXISTS idx_disp_member ON dispensations (member_id);
CREATE INDEX IF NOT EXISTS idx_disp_preparation ON dispensations (preparation_id);
CREATE INDEX IF NOT EXISTS idx_disp_date ON dispensations (dispensed_at);


-- ============================================================================
-- Fim da migration 028. O runner registra versao e checksum em
-- schema_migrations; nao e necessario INSERT manual aqui.
--
-- NOTA: em ambiente de producao (Render), se o usuario DB nao tiver
-- permissao para CREATE EXTENSION, rodar uma vez manualmente:
--   CREATE EXTENSION postgis;
-- no dashboard do Render ANTES de aplicar esta migration.
-- ============================================================================
