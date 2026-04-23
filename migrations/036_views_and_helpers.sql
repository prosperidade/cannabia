-- Migration 036: Views e funcoes helper (F6.2 do docs/BACKLOG_SCC.md)
--
-- Implementa as views e funcoes sugeridas em
-- docs/25_SCC_DATA_MODEL_AND_MIGRATIONS.md secao 12:
--
--   12.1  v_member_active_prescriptions  — associados ativos com
--                                           prescricao valida.
--   12.2  v_traceability_chain_status    — estado de cada chain
--                                           (ultimo evento, hash, sequencia).
--   12.3  v_sandbox_indicator_dashboard  — indicadores consolidados.
--   12.4  fn_generate_event_hash         — sha256 canonico de evento.
--   12.5  fn_verify_chain_integrity      — verifica continuidade de cadeia.
--
-- DECISOES DE PROJETO:
--
--  * v_sandbox_indicator_dashboard e REGULAR view, nao MATERIALIZED.
--    O doc 25 §12.3 sugere materializada para perf de dashboard, mas
--    materializada exige REFRESH (manual ou via cron) e pode servir
--    dados stale. Para v1, dados sempre frescos e mais importante que
--    micro-perf — quando o volume justificar, converter para
--    materialized em migration futura (037+) e adicionar REFRESH no
--    cron. Indexes de F6.1 (idx_siv_indicator_period_desc) ja sustentam
--    a query.
--
--  * fn_generate_event_hash usa sha256() built-in do Postgres 11+
--    + encode(...,'hex'), sem dependencia de pgcrypto. Canonicalizacao
--    do JSONB e por payload::text — Postgres normaliza JSONB ao
--    armazenar, entao a string e estavel para o mesmo conteudo logico.
--
--  * Numeracao 036: o BACKLOG_SCC originalmente reservava 035, mas o
--    deslocamento iniciado pela 035_indexes_and_performance (que tomou
--    o slot 034 do BACKLOG por colisao com review_workflows) propaga.
--
-- Idempotente: CREATE OR REPLACE em views e funcoes; DROP VIEW IF
-- EXISTS antes do CREATE so quando a definicao mudar de forma que
-- CREATE OR REPLACE nao consegue substituir (ex.: mudanca de colunas).
-- ============================================================================


-- ---------------------------------------------------------------------------
-- 12.1  v_member_active_prescriptions
--
-- Associados com membership_status='active' E ainda nao terminados,
-- com prescricao_on_file ainda valida (status='active' AND not expired).
-- Validade calculada como prescriptions.created_at +
-- prescriptions.validity_days * INTERVAL '1 day'.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_member_active_prescriptions AS
SELECT
    am.id                          AS member_id,
    am.tenant_id,
    am.patient_id,
    am.membership_number,
    am.membership_status,
    am.joined_at,
    am.prescription_on_file_id     AS prescription_id,
    p.cannabinoid_ratio,
    p.spectrum,
    p.administration_route,
    p.concentration_mg_ml,
    p.max_daily_mg,
    p.doctor_name,
    p.doctor_crm,
    p.created_at                   AS prescription_issued_at,
    (p.created_at + (p.validity_days || ' days')::interval)
                                   AS prescription_expires_at,
    p.status                       AS prescription_status
FROM association_members am
JOIN prescriptions p ON p.id = am.prescription_on_file_id
WHERE am.membership_status = 'active'
  AND am.terminated_at IS NULL
  AND p.status = 'active'
  AND (p.created_at + (p.validity_days || ' days')::interval) > NOW();


-- ---------------------------------------------------------------------------
-- 12.2  v_traceability_chain_status
--
-- Para cada chain_id: tenant_id, total de eventos, ultima sequencia,
-- timestamp do ultimo evento, event_hash do ultimo evento.
--
-- Implementacao: agregacao + JOIN no max(chain_sequence) para puxar o
-- event_hash correspondente. Index (chain_id, chain_sequence) UNIQUE
-- da migration 029 sustenta a query.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_traceability_chain_status AS
SELECT
    te.chain_id,
    te.tenant_id,
    COUNT(*)                       AS total_events,
    MAX(te.chain_sequence)         AS last_sequence,
    MAX(te.occurred_at)            AS last_occurred_at,
    -- event_hash do ultimo evento da cadeia
    (SELECT te2.event_hash
       FROM traceability_events te2
      WHERE te2.chain_id = te.chain_id
      ORDER BY te2.chain_sequence DESC
      LIMIT 1)                     AS last_event_hash,
    MIN(te.occurred_at)            AS first_occurred_at
FROM traceability_events te
GROUP BY te.chain_id, te.tenant_id;


-- ---------------------------------------------------------------------------
-- 12.3  v_sandbox_indicator_dashboard  (regular view, ver decisao acima)
--
-- Para cada indicador: ultimo valor calculado, target, status (on_target
-- = true se latest_value satisfaz target dentro da tolerancia padrao de
-- 5%), n de periodos disponiveis.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_sandbox_indicator_dashboard AS
WITH latest AS (
    SELECT DISTINCT ON (siv.indicator_id)
        siv.indicator_id,
        siv.calculated_value      AS latest_value,
        siv.period_start          AS latest_period_start,
        siv.period_end            AS latest_period_end,
        siv.calculated_at         AS latest_calculated_at
      FROM sandbox_indicator_values siv
     ORDER BY siv.indicator_id, siv.period_start DESC
),
counts AS (
    SELECT indicator_id, COUNT(*) AS n_periods
      FROM sandbox_indicator_values
     GROUP BY indicator_id
)
SELECT
    si.id                          AS indicator_id,
    si.project_id,
    sp.tenant_id,
    si.indicator_code,
    si.indicator_name,
    si.unit,
    si.target_value,
    si.reporting_frequency,
    si.is_mandatory,
    l.latest_value,
    l.latest_period_start,
    l.latest_period_end,
    l.latest_calculated_at,
    COALESCE(c.n_periods, 0)       AS n_periods,
    -- on_target: NULL se sem target ou sem latest_value;
    -- caso contrario, true se diff relativa <= 5%.
    CASE
      WHEN si.target_value IS NULL OR l.latest_value IS NULL THEN NULL
      WHEN si.target_value = 0 THEN (l.latest_value = 0)
      ELSE (
        ABS(l.latest_value - si.target_value) / ABS(si.target_value) <= 0.05
      )
    END                            AS on_target
FROM sandbox_indicators si
JOIN sandbox_projects sp ON sp.id = si.project_id
LEFT JOIN latest l ON l.indicator_id = si.id
LEFT JOIN counts c ON c.indicator_id = si.id;


-- ---------------------------------------------------------------------------
-- 12.4  fn_generate_event_hash
--
-- Hash canonico para tabelas de eventos (usado em traceability_events,
-- audit_trail derivado, etc). Determinístico:
--   SHA-256(payload_canonical || COALESCE(previous_hash, ''))  em hex.
--
-- Aceita previous_hash NULL (primeiro evento da cadeia).
-- Retorna char(64) hex lowercase, mesmo formato usado nas colunas
-- traceability_events.event_hash / previous_hash.
--
-- payload_canonical = payload::text — Postgres JSONB normaliza chaves
-- e formatacao ao armazenar, entao a saida text e estavel para o mesmo
-- conteudo logico (testes em test_views_and_helpers cobrem isso).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_generate_event_hash(
    payload       JSONB,
    previous_hash CHAR(64) DEFAULT NULL
)
RETURNS CHAR(64)
LANGUAGE SQL
IMMUTABLE
AS $$
    SELECT encode(
        sha256(
            (payload::text || COALESCE(previous_hash, ''))::bytea
        ),
        'hex'
    )::char(64);
$$;


-- ---------------------------------------------------------------------------
-- 12.5  fn_verify_chain_integrity
--
-- Verifica continuidade de uma cadeia de traceability_events. Para cada
-- evento da cadeia (em ordem de chain_sequence):
--
--   - Sequence 1: previous_hash deve ser NULL.
--   - Sequence > 1: previous_hash deve ser igual ao event_hash do
--                   evento anterior (chain_sequence - 1).
--
-- Retorna uma TABLE com 1 linha por evento, com flag valid e
-- expected_previous para diagnostico de adulteracao.
--
-- Uso tipico:
--   SELECT * FROM fn_verify_chain_integrity('lot-2026-001')
--   WHERE NOT valid;
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_verify_chain_integrity(p_chain_id VARCHAR(128))
RETURNS TABLE (
    chain_sequence    BIGINT,
    event_id          BIGINT,
    actual_previous   CHAR(64),
    expected_previous CHAR(64),
    valid             BOOLEAN
)
LANGUAGE SQL
STABLE
AS $$
    WITH chain AS (
        SELECT
            te.id,
            te.chain_sequence,
            te.event_hash,
            te.previous_hash,
            LAG(te.event_hash) OVER (ORDER BY te.chain_sequence)
                AS expected_previous
        FROM traceability_events te
        WHERE te.chain_id = p_chain_id
    )
    SELECT
        chain.chain_sequence,
        chain.id AS event_id,
        chain.previous_hash AS actual_previous,
        chain.expected_previous,
        CASE
            WHEN chain.chain_sequence = 1 THEN chain.previous_hash IS NULL
            ELSE chain.previous_hash IS NOT DISTINCT FROM chain.expected_previous
        END AS valid
    FROM chain
    ORDER BY chain.chain_sequence;
$$;


-- ============================================================================
-- Fim da migration 036. O runner registra versao e checksum em
-- schema_migrations; nao e necessario INSERT manual aqui.
-- ============================================================================
