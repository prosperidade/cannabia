-- Migration 041: Casos clinicos agregados anonimizados (C7).
--
-- Decisao da C7: a base cientifica deve crescer com o uso real do produto.
-- Os agentes Anamnese/Tratamento/Prescritor ja gravam dados estruturados
-- de cada paciente — mas isolados. Falta um agregado longitudinal
-- anonimizado que vire material indexavel.
--
-- Aproveitamos a tabela `knowledge_catalog` ja existente (single source
-- of truth para RAG) e adicionamos um campo `case_aggregate_metadata`
-- JSONB para guardar o contexto estruturado do caso agregado:
--
--   {
--     "k_anonymity_n": 12,                -- numero de pacientes na coorte
--     "condition": "epilepsia_refrataria",
--     "age_range": "30-49",
--     "dose_range": "5-10mg",
--     "ratio_class": "cbd_dominante",
--     "period_start": "2025-10-01",
--     "period_end": "2026-04-29",
--     "metrics": {
--       "adverse_events_pct": 0.17,
--       "retention_d15_pct": 0.92,
--       "median_dose_mg": 7
--     },
--     "tenants_contributing": 3
--   }
--
-- doc_type='case_aggregate' identifica esses registros e permite filtrar
-- na UI. Mantem-se imune a re-identificacao pelo threshold k>=5.
--
-- Idempotente.
-- ============================================================================

BEGIN;

ALTER TABLE knowledge_catalog
    ADD COLUMN IF NOT EXISTS case_aggregate_metadata JSONB DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_knowledge_catalog_case_aggregate_metadata
    ON knowledge_catalog USING GIN (case_aggregate_metadata)
    WHERE case_aggregate_metadata IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_knowledge_catalog_doc_type_case_aggregate
    ON knowledge_catalog (doc_type)
    WHERE doc_type = 'case_aggregate';

COMMIT;
