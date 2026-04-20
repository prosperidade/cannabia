-- Migration 027: Quality Schema (F2.2 do docs/BACKLOG_SCC.md)
--
-- Cria as 6 tabelas do dominio `quality` previstas no
-- docs/25_SCC_DATA_MODEL_AND_MIGRATIONS.md secoes 6.1 a 6.4:
--
--   6.1  sops + sop_versions        — procedimentos e versionamento
--   6.2  sop_trainings              — treinamento de usuarios por versao
--   6.3  sop_evidences              — execucoes (APPEND-ONLY, doc §2.4/§7.7)
--   6.4  sop_deviations + capa_actions — desvios e acoes corretivas/preventivas
--
-- Complicacoes resolvidas nesta migration:
--
-- 1. FK CIRCULAR entre sops e sop_versions:
--      sop_versions.sop_id -> sops.id
--      sops.current_version_id -> sop_versions.id
--    Criamos sops SEM a FK de current_version_id; depois criamos sop_versions
--    com a FK para sops; depois adicionamos a FK de volta via ALTER TABLE
--    (em DO $$ com pg_constraint guard para idempotencia).
--
-- 2. APPEND-ONLY em sop_evidences (doc §2.4 + §7.7):
--    Doc 25 §7.7 define `prevent_update_delete()` como funcao compartilhada
--    entre sop_evidences e traceability_events. Criamos a funcao aqui (CREATE
--    OR REPLACE) e aplicamos o trigger em sop_evidences imediatamente — lockar
--    desde a criacao evita janela de vulnerabilidade entre 027 e 030.
--    Quando 030 rodar, vai reusar a mesma funcao para traceability_events.
--
-- Dependencias externas:
--   - tenants(id)  — evoluida em 024
--   - users(id)    — foundation
--
-- Idempotencia: CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT EXISTS,
-- CREATE OR REPLACE FUNCTION, DO $$ pg_constraint/pg_trigger guards.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- 1. sops  (doc 25 §6.1) — criada SEM fk_sops_current_version (resolvida no final)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sops (
    id                 SERIAL PRIMARY KEY,
    tenant_id          INT NOT NULL REFERENCES tenants(id),
    code               VARCHAR(64) NOT NULL,
    title              VARCHAR(255) NOT NULL,
    area               VARCHAR(64) NOT NULL,
    current_version_id INT,  -- FK adicionada apos sop_versions existir
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sops_tenant_code UNIQUE (tenant_id, code)
);

CREATE INDEX IF NOT EXISTS idx_sops_tenant ON sops (tenant_id);
CREATE INDEX IF NOT EXISTS idx_sops_area ON sops (area);


-- ---------------------------------------------------------------------------
-- 2. sop_versions  (doc 25 §6.1)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sop_versions (
    id              SERIAL PRIMARY KEY,
    sop_id          INT NOT NULL REFERENCES sops(id),
    version_number  VARCHAR(32) NOT NULL,
    content_uri     TEXT NOT NULL,
    content_hash    CHAR(64) NOT NULL,
    effective_from  DATE NOT NULL,
    effective_until DATE,
    approved_by     INT REFERENCES users(id),
    approved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sop_versions UNIQUE (sop_id, version_number),
    CONSTRAINT chk_sop_versions_effective_order CHECK (
        effective_until IS NULL OR effective_until >= effective_from
    )
);

CREATE INDEX IF NOT EXISTS idx_sop_versions_sop ON sop_versions (sop_id);


-- ---------------------------------------------------------------------------
-- 3. Fecha o ciclo: sops.current_version_id -> sop_versions.id
-- DO $$ com pg_constraint para idempotencia em re-execucoes.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_sops_current_version'
    ) THEN
        ALTER TABLE sops
          ADD CONSTRAINT fk_sops_current_version
          FOREIGN KEY (current_version_id) REFERENCES sop_versions(id);
    END IF;
END
$$;


-- ---------------------------------------------------------------------------
-- 4. sop_trainings  (doc 25 §6.2)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sop_trainings (
    id             SERIAL PRIMARY KEY,
    sop_version_id INT NOT NULL REFERENCES sop_versions(id),
    user_id        INT NOT NULL REFERENCES users(id),
    trained_at     TIMESTAMPTZ NOT NULL,
    evidence_uri   TEXT,
    evidence_hash  CHAR(64),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sop_trainings UNIQUE (sop_version_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_sop_trainings_version ON sop_trainings (sop_version_id);
CREATE INDEX IF NOT EXISTS idx_sop_trainings_user ON sop_trainings (user_id);


-- ---------------------------------------------------------------------------
-- 5. sop_evidences  (doc 25 §6.3) — APPEND-ONLY
--
-- BIGSERIAL porque a tabela vai crescer indefinidamente (cada execucao de SOP
-- gera uma linha; ambiente clinico gera milhares por dia em escala).
-- UNIQUE (chain_id, chain_sequence) forca sequenciamento dentro de cada cadeia.
-- chain_sequence >= 1 (primeiro evento da cadeia nunca e 0).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sop_evidences (
    id                 BIGSERIAL PRIMARY KEY,
    tenant_id          INT NOT NULL REFERENCES tenants(id),
    sop_version_id     INT NOT NULL REFERENCES sop_versions(id),
    executed_by        INT REFERENCES users(id),
    execution_context  JSONB NOT NULL,
    related_event_type VARCHAR(64),
    related_event_id   BIGINT,
    chain_id           VARCHAR(128) NOT NULL,
    chain_sequence     BIGINT NOT NULL,
    event_hash         CHAR(64) NOT NULL,
    previous_hash      CHAR(64),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sop_evidences_chain UNIQUE (chain_id, chain_sequence),
    CONSTRAINT chk_sop_evidences_sequence CHECK (chain_sequence >= 1)
);

CREATE INDEX IF NOT EXISTS idx_sop_ev_tenant ON sop_evidences (tenant_id);
CREATE INDEX IF NOT EXISTS idx_sop_ev_version ON sop_evidences (sop_version_id);
CREATE INDEX IF NOT EXISTS idx_sop_ev_created ON sop_evidences (created_at);


-- ---------------------------------------------------------------------------
-- 6. Funcao e trigger de protecao append-only  (doc 25 §2.4 + §7.7)
--
-- Funcao compartilhada entre sop_evidences (aqui) e traceability_events
-- (migration 030). CREATE OR REPLACE FUNCTION e idempotente — se 030 rodar
-- depois, substitui com o mesmo corpo sem efeito colateral.
--
-- Trigger especifico de sop_evidences fica guardado por DO $$ pg_trigger para
-- permitir re-execucao da migration.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION prevent_update_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Table % is append-only. Updates and deletes are forbidden.', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'sop_evidences_immutable'
    ) THEN
        CREATE TRIGGER sop_evidences_immutable
            BEFORE UPDATE OR DELETE ON sop_evidences
            FOR EACH ROW EXECUTE FUNCTION prevent_update_delete();
    END IF;
END
$$;


-- ---------------------------------------------------------------------------
-- 7. sop_deviations  (doc 25 §6.4)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sop_deviations (
    id             SERIAL PRIMARY KEY,
    tenant_id      INT NOT NULL REFERENCES tenants(id),
    sop_version_id INT NOT NULL REFERENCES sop_versions(id),
    deviation_date TIMESTAMPTZ NOT NULL,
    severity       VARCHAR(16) NOT NULL,
    description    TEXT NOT NULL,
    detected_by    INT REFERENCES users(id),
    status         VARCHAR(32) NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_sop_deviations_severity CHECK (
        severity IN ('low', 'medium', 'high', 'critical')
    ),
    CONSTRAINT chk_sop_deviations_status CHECK (
        status IN ('open', 'investigating', 'capa_pending', 'resolved', 'closed')
    )
);

CREATE INDEX IF NOT EXISTS idx_sop_dev_tenant ON sop_deviations (tenant_id);
CREATE INDEX IF NOT EXISTS idx_sop_dev_version ON sop_deviations (sop_version_id);
CREATE INDEX IF NOT EXISTS idx_sop_dev_status ON sop_deviations (status);


-- ---------------------------------------------------------------------------
-- 8. capa_actions  (doc 25 §6.4)
--
-- CHECK defensivo em completed_at >= due_date NAO faz sentido (pode-se
-- concluir antes do prazo). Mas completed_at nunca deveria ser antes do
-- created_at — isso sim e uma inversao temporal incoerente.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS capa_actions (
    id                  SERIAL PRIMARY KEY,
    deviation_id        INT NOT NULL REFERENCES sop_deviations(id),
    action_type         VARCHAR(16) NOT NULL,
    description         TEXT NOT NULL,
    responsible         INT REFERENCES users(id),
    due_date            DATE NOT NULL,
    completed_at        TIMESTAMPTZ,
    effectiveness_check TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_capa_action_type CHECK (
        action_type IN ('corrective', 'preventive')
    ),
    CONSTRAINT chk_capa_completion_order CHECK (
        completed_at IS NULL OR completed_at >= created_at
    )
);

CREATE INDEX IF NOT EXISTS idx_capa_deviation ON capa_actions (deviation_id);
CREATE INDEX IF NOT EXISTS idx_capa_due_date ON capa_actions (due_date);


-- ============================================================================
-- Fim da migration 027. O runner registra versao e checksum em
-- schema_migrations; nao e necessario INSERT manual aqui.
-- ============================================================================
