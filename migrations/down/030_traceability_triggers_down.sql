-- Down migration 030: reverter Traceability Triggers
--
-- Reverte os dois triggers de traceability_events + a funcao
-- validate_chain_continuity. NAO dropa prevent_update_delete (funcao
-- compartilhada com sop_evidences em 027).
--
-- ATENCAO:
--
-- Apos este down, traceability_events volta a aceitar UPDATE/DELETE e
-- nao valida mais continuidade de cadeia em INSERT. Em ambiente com
-- dados reais, isso abre brecha para violar imutabilidade regulatoria.
-- So usar este down em ambientes controlados (dev/test) ou como primeiro
-- passo para down da 029.
--
-- Idempotente: DROP ... IF EXISTS.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Triggers
-- ---------------------------------------------------------------------------
DROP TRIGGER IF EXISTS traceability_events_chain_check ON traceability_events;
DROP TRIGGER IF EXISTS traceability_events_immutable ON traceability_events;


-- ---------------------------------------------------------------------------
-- Funcao especifica desta migration
--
-- prevent_update_delete NAO e dropada — continua em uso por
-- sop_evidences_immutable (criado em 027).
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS validate_chain_continuity();


-- ============================================================================
-- Fim do down 030. Apos executar, remova manualmente o registro:
--   DELETE FROM schema_migrations WHERE version = '030';
-- ============================================================================
