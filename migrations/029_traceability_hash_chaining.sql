-- Migration 029: Traceability Events + Hash Chaining (Fase 2 do SCC)
--
-- Cria a tabela `traceability_events` prevista no doc 25 §7.6 — a tabela
-- central do schema de rastreabilidade. Cada operacao relevante (plantio,
-- colheita, extracao, preparacao, dispensacao, movimentacao) gera um
-- evento imutavel com hash chaining.
--
-- Esta migration foca SO na estrutura + constraints estaticas. Os elementos
-- dinamicos ficam em 030:
--   - Trigger append-only (prevent_update_delete, funcao ja existe em 027)
--   - Trigger de validacao de cadeia (validate_chain_continuity, doc §7.8)
--
-- A separacao existe porque os triggers tem implicacoes operacionais
-- (bloqueiam UPDATE/DELETE, validam referencias) que merecem migration
-- dedicada — o doc 25 §11.1 explicitamente separa 029/030 nessa ordem.
--
-- Dependencias externas (criadas em migrations anteriores):
--   - tenants(id)  — 024
--   - users(id)    — foundation
--   - postgis      — 028 (GEOGRAPHY column)
--
-- Idempotencia: CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT EXISTS.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- traceability_events  (doc 25 §7.6)
--
-- BIGSERIAL porque a tabela vai acumular milhoes de eventos por tenant ao
-- longo do ciclo de vida regulatorio. Two UNIQUE constraints:
--   - (chain_id, chain_sequence): garante sequenciamento dentro da cadeia
--   - event_hash: garante que nao existem dois eventos com mesmo hash
--     (colisao = bug ou ataque)
--
-- CHECK chain_sequence >= 1 (mesmo pattern de sop_evidences em 027):
-- sequencia comeca em 1, nao em 0.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS traceability_events (
    id             BIGSERIAL PRIMARY KEY,
    tenant_id      INT NOT NULL REFERENCES tenants(id),
    event_type     VARCHAR(64) NOT NULL,
    subject_type   VARCHAR(32) NOT NULL,
    subject_id     BIGINT NOT NULL,
    actor_user_id  INT REFERENCES users(id),
    actor_role     VARCHAR(64),
    geo_reference  GEOGRAPHY(POINT, 4326),
    payload        JSONB NOT NULL,
    chain_id       VARCHAR(128) NOT NULL,
    chain_sequence BIGINT NOT NULL,
    event_hash     CHAR(64) NOT NULL,
    previous_hash  CHAR(64),
    occurred_at    TIMESTAMPTZ NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_trace_chain UNIQUE (chain_id, chain_sequence),
    CONSTRAINT uq_trace_event_hash UNIQUE (event_hash),
    CONSTRAINT chk_trace_sequence CHECK (chain_sequence >= 1)
);


-- ---------------------------------------------------------------------------
-- Indexes (doc 25 §7.6) — 5 indexes para queries comuns do dominio:
--   - por tenant (isolamento multi-tenant)
--   - por chain (walking da cadeia)
--   - por subject (o que aconteceu com uma entidade especifica)
--   - por event_type (filtrar eventos de um tipo em analytics)
--   - por occurred_at (janelas temporais em relatorios regulatorios)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_trace_tenant ON traceability_events (tenant_id);
CREATE INDEX IF NOT EXISTS idx_trace_chain ON traceability_events (chain_id);
CREATE INDEX IF NOT EXISTS idx_trace_subject
    ON traceability_events (subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_trace_type ON traceability_events (event_type);
CREATE INDEX IF NOT EXISTS idx_trace_occurred
    ON traceability_events (occurred_at);


-- ============================================================================
-- Fim da migration 029. Triggers de protecao e validacao de cadeia ficam
-- em 030_traceability_triggers.sql. Ate la, a tabela aceita UPDATE/DELETE
-- e nao valida continuidade da cadeia — nao inserir dados reais antes de
-- 030 estar aplicada em producao.
-- ============================================================================
