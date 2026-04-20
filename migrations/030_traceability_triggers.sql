-- Migration 030: Traceability Triggers (Fase 2 do SCC)
--
-- Aplica os dois triggers criticos de traceability_events (doc 25 §§7.7-7.8):
--
--   7.7  traceability_events_immutable  — protecao append-only
--         (reusa prevent_update_delete criada em 027)
--   7.8  traceability_events_chain_check — validacao de continuidade de hash
--         (cria validate_chain_continuity aqui, especifica desta tabela)
--
-- Apos esta migration, traceability_events:
--   - Bloqueia UPDATE e DELETE via trigger BEFORE UPDATE OR DELETE.
--   - Valida em BEFORE INSERT que NEW.previous_hash bate com o event_hash
--     do evento anterior na mesma cadeia (chain_id, chain_sequence - 1).
--
-- Semantica da validacao de continuidade (doc 25 §7.8):
--   - Se NEW.chain_sequence = 1: primeiro evento da cadeia, nao valida.
--   - Se NEW.chain_sequence > 1:
--       expected = SELECT event_hash WHERE chain_id = NEW.chain_id
--                                      AND chain_sequence = NEW.chain_sequence - 1
--       Se NEW.previous_hash IS DISTINCT FROM expected: RAISE.
--
-- Limitacao conhecida: se o evento anterior (seq - 1) nao existir, expected
-- sera NULL e a checagem passa se NEW.previous_hash tambem for NULL. Isso
-- permite "gaps" na cadeia (ex.: inserir seq 1 e depois seq 5 sem os
-- intermediarios). UNIQUE(chain_id, chain_sequence) impede duplicatas mas
-- nao exige contiguidade. Prevenir gaps requer logica adicional a nivel de
-- aplicacao ou outro trigger (fora do escopo do doc 25).
--
-- Dependencias:
--   - traceability_events  — 029
--   - prevent_update_delete — funcao criada em 027
--
-- Idempotencia: CREATE OR REPLACE FUNCTION (validate_chain_continuity) +
-- DO $$ com pg_trigger guard para cada CREATE TRIGGER.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- 1. traceability_events_immutable — trigger append-only
--
-- Reusa prevent_update_delete() de 027 (ver comentario de 027 sobre o fato
-- de ser funcao compartilhada entre sop_evidences e traceability_events).
-- Lockando UPDATE e DELETE desde que esta migration rode.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'traceability_events_immutable'
    ) THEN
        CREATE TRIGGER traceability_events_immutable
            BEFORE UPDATE OR DELETE ON traceability_events
            FOR EACH ROW EXECUTE FUNCTION prevent_update_delete();
    END IF;
END
$$;


-- ---------------------------------------------------------------------------
-- 2. validate_chain_continuity() — funcao de validacao
--
-- CREATE OR REPLACE porque e especifica de traceability_events; se a
-- migration for re-executada, substitui com o mesmo corpo (sem efeito).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION validate_chain_continuity()
RETURNS TRIGGER AS $$
DECLARE
    expected_previous CHAR(64);
BEGIN
    SELECT event_hash INTO expected_previous
      FROM traceability_events
     WHERE chain_id = NEW.chain_id
       AND chain_sequence = NEW.chain_sequence - 1;

    IF NEW.chain_sequence > 1
       AND NEW.previous_hash IS DISTINCT FROM expected_previous THEN
        RAISE EXCEPTION
            'Chain continuity violation on chain %, sequence %: expected previous_hash %, got %',
            NEW.chain_id, NEW.chain_sequence, expected_previous, NEW.previous_hash;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ---------------------------------------------------------------------------
-- 3. traceability_events_chain_check — BEFORE INSERT trigger
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'traceability_events_chain_check'
    ) THEN
        CREATE TRIGGER traceability_events_chain_check
            BEFORE INSERT ON traceability_events
            FOR EACH ROW EXECUTE FUNCTION validate_chain_continuity();
    END IF;
END
$$;


-- ============================================================================
-- Fim da migration 030. A partir daqui, traceability_events e imutavel e
-- auto-valida continuidade de hash na insercao. Dados pre-existentes nao
-- sao revalidados — integridade historica fica a cargo de
-- fn_verify_chain_integrity (doc 25 §12.5, fora do escopo desta migration).
-- ============================================================================
