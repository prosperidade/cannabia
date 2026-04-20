-- Down migration 027: reverter Quality Schema
--
-- Reverte a criacao das 6 tabelas do dominio `quality` + trigger
-- append-only + funcao compartilhada.
--
-- ATENCAO — perda informacional:
--
-- Dropar sop_evidences destroi registros de execucoes de SOP que sao
-- evidencia regulatoria (BPF, ISO, sandbox). Em ambiente com dados reais
-- isso tem implicacoes legais serias — o caminho oficial para voltar a
-- um estado anterior com dados e restore por backup, ver
-- docs/BACKUP_AND_DISASTER_RECOVERY.md §4.
--
-- `tenants` e `users` nao sao tocadas (existiam antes da 027).
--
-- Ordem de drop e INVERSA a ordem de criacao, respeitando FKs:
--
--   capa_actions          -> sop_deviations
--   sop_deviations        -> sop_versions
--   sop_evidences         -> sop_versions (+ trigger append-only)
--   sop_trainings         -> sop_versions
--   sops <-> sop_versions  (FK circular: precisa dropar fk_sops_current_version
--                           antes de dropar sop_versions)
--
-- A funcao `prevent_update_delete()` e compartilhada com traceability_events
-- (migration 030). Se 030 ja foi aplicada, NAO podemos dropar a funcao aqui
-- porque vai quebrar a trigger de traceability_events. O down checa se a
-- funcao esta sendo usada por outros triggers antes de dropar.
--
-- Idempotente: todos os DROPs usam IF EXISTS e CASCADE onde necessario.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Tabelas (em ordem reversa da criacao, respeitando FKs)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS capa_actions;
DROP TABLE IF EXISTS sop_deviations;

-- Drop explicito do trigger antes da tabela (drop da tabela ja dropa o
-- trigger em cascata, mas deixar explicito torna o log de down auditavel).
DROP TRIGGER IF EXISTS sop_evidences_immutable ON sop_evidences;
DROP TABLE IF EXISTS sop_evidences;

DROP TABLE IF EXISTS sop_trainings;

-- FK circular: dropar fk_sops_current_version antes de dropar sop_versions,
-- senao a FK trava o drop. Alternativa seria DROP TABLE ... CASCADE mas a
-- forma explicita e mais segura (nao arrasta outras tabelas por engano).
ALTER TABLE sops DROP CONSTRAINT IF EXISTS fk_sops_current_version;
DROP TABLE IF EXISTS sop_versions;
DROP TABLE IF EXISTS sops;


-- ---------------------------------------------------------------------------
-- Funcao compartilhada — drop condicional
--
-- Se houver outros triggers usando prevent_update_delete (ex.:
-- traceability_events_immutable da 030), NAO dropa. O DO $$ checa em
-- pg_trigger antes de dropar.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger t
        JOIN pg_proc p ON t.tgfoid = p.oid
        WHERE p.proname = 'prevent_update_delete'
    ) THEN
        DROP FUNCTION IF EXISTS prevent_update_delete();
    END IF;
END
$$;


-- ============================================================================
-- Fim do down 027. Apos executar, remova manualmente o registro:
--   DELETE FROM schema_migrations WHERE version = '027';
-- ============================================================================
