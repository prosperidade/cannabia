-- Migration 033: Crypto Schema (F5.1 do docs/BACKLOG_SCC.md)
--
-- Cria as 2 tabelas do dominio crypto previstas no
-- docs/25_SCC_DATA_MODEL_AND_MIGRATIONS.md secoes 10.1 e 10.2:
--
--   10.1  blockchain_anchors     — registro de cada ancoragem Merkle em
--                                  blockchain publica (Bitcoin/Polygon/Ethereum)
--   10.2  anchor_event_mappings  — mapa N:N de eventos cobertos por ancoragem
--                                  com Merkle proof por evento
--
-- Dependencias externas (ja criadas):
--   - tenants(id) — 024
--
-- blockchain_anchors.tenant_id e NULLABLE para suportar ``anchor_scope =
-- 'global'`` — ancoragens globais da plataforma cobrem eventos de
-- multiplos tenants. Ancoragens 'tenant' e 'project' devem ter tenant_id
-- preenchido (nao e enforceado via CHECK aqui porque um CHECK condicional
-- por scope adicionaria acoplamento ruim; a validacao fica na camada de
-- servico em F5.2).
--
-- BIGSERIAL em blockchain_anchors.id porque ancoragens sao diarias por
-- tenant + escopo; em projetos de longa duracao acumulam rapido. BIGINT
-- em anchor_event_mappings porque um unico anchor pode mapear milhoes de
-- traceability_events.
--
-- Idempotencia: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- 1. blockchain_anchors  (doc 25 §10.1)
--
-- verification_status transita: pending → confirmed (apos o block finalizar
-- na rede) ou → failed (erro de submissao, reorganizacao, etc.). Coluna
-- e mutavel por design (sem trigger append-only) para permitir a
-- confirmacao assincrona apos o block mining.
--
-- CHECKs defensivos:
--   covered_until >= covered_from         (janela de cobertura coerente)
--   events_count >= 0                     (contagem nao-negativa)
--   verified_at IS NULL OR verified_at >= anchored_at (verificacao pos-registro)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS blockchain_anchors (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           INT REFERENCES tenants(id),
    anchor_scope        VARCHAR(32) NOT NULL,
    covered_from        TIMESTAMPTZ NOT NULL,
    covered_until       TIMESTAMPTZ NOT NULL,
    events_count        BIGINT NOT NULL,
    merkle_root         CHAR(64) NOT NULL,
    blockchain_network  VARCHAR(32) NOT NULL,
    transaction_id      VARCHAR(255) NOT NULL,
    block_number        BIGINT,
    block_timestamp     TIMESTAMPTZ,
    proof_uri           TEXT,
    proof_hash          CHAR(64),
    anchored_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at         TIMESTAMPTZ,
    verification_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    CONSTRAINT chk_anchors_scope CHECK (
        anchor_scope IN ('global', 'tenant', 'project')
    ),
    CONSTRAINT chk_anchors_network CHECK (
        blockchain_network IN ('bitcoin_ots', 'polygon', 'ethereum')
    ),
    CONSTRAINT chk_anchors_verification CHECK (
        verification_status IN ('pending', 'confirmed', 'failed')
    ),
    CONSTRAINT chk_anchors_coverage_order CHECK (
        covered_until >= covered_from
    ),
    CONSTRAINT chk_anchors_events_count CHECK (
        events_count >= 0
    ),
    CONSTRAINT chk_anchors_verification_order CHECK (
        verified_at IS NULL OR verified_at >= anchored_at
    )
);

CREATE INDEX IF NOT EXISTS idx_anchors_tenant
    ON blockchain_anchors (tenant_id);
CREATE INDEX IF NOT EXISTS idx_anchors_period
    ON blockchain_anchors (covered_from, covered_until);
CREATE INDEX IF NOT EXISTS idx_anchors_network
    ON blockchain_anchors (blockchain_network);


-- ---------------------------------------------------------------------------
-- 2. anchor_event_mappings  (doc 25 §10.2)
--
-- Cada linha = prova de inclusao de um evento especifico na arvore Merkle
-- de uma ancoragem. ``event_table`` e ``event_id`` sao uma FK polimorfica
-- (qualquer tabela de evento — traceability_events, adverse_events,
-- dispensations, etc.) sem constraint relacional; integridade fica a
-- cargo do servico.
--
-- ``merkle_path`` JSONB guarda o path de hashes irmaos necessario para
-- reconstruir a raiz a partir do event_hash, permitindo verificacao
-- independente sem acesso a toda a arvore.
--
-- PK composta garante idempotencia de insercao (mesmo evento mapeado duas
-- vezes na mesma ancoragem borbulha violation).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS anchor_event_mappings (
    anchor_id   BIGINT NOT NULL REFERENCES blockchain_anchors(id),
    event_table VARCHAR(64) NOT NULL,
    event_id    BIGINT NOT NULL,
    event_hash  CHAR(64) NOT NULL,
    merkle_path JSONB NOT NULL,
    CONSTRAINT pk_anchor_event_mappings PRIMARY KEY (anchor_id, event_table, event_id)
);

-- Index auxiliar para lookup reverso (dado um evento, qual ancoragem cobre?)
CREATE INDEX IF NOT EXISTS idx_anchor_mappings_event
    ON anchor_event_mappings (event_table, event_id);


-- ============================================================================
-- Fim da migration 033.
-- ============================================================================
