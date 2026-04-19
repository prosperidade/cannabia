-- Migration 023: Timestamp Standardization (P0.2 do docs/BACKLOG_SCC.md)
--
-- Padroniza TIMESTAMP -> TIMESTAMPTZ nas colunas criadas pelas migrations
-- legadas 001_initial_schema.sql e 003_anamnesis_reports.sql. A ausencia
-- de fuso-horario nessas colunas produz inconsistencias em operacoes
-- cross-table que usam NOW() (TIMESTAMPTZ) e em ambientes com mais de uma
-- zona de tempo (producao UTC vs. dev local).
--
-- Estrategia:
--   - ALTER COLUMN ... TYPE TIMESTAMPTZ USING <coluna> AT TIME ZONE 'UTC'
--     converte os valores assumindo que os timestamps existentes foram
--     gravados em UTC (pressuposto valido: servidor Render opera em UTC e
--     os defaults usam CURRENT_TIMESTAMP sobre uma conexao UTC).
--   - DEFAULT CURRENT_TIMESTAMP permanece valido em TIMESTAMPTZ; mantemos
--     o default para nao perturbar rows criadas entre migrations.
--   - Idempotente: cada ALTER verifica o tipo atual via information_schema
--     antes de converter, permitindo reexecucao segura.
--
-- Escopo (tabelas com TIMESTAMP legado em 001/003):
--   001 -> clinics, patients, ai_prompt_versions, users, user_clinics,
--          appointments, message_status_updates, ai_audit_logs, alerts,
--          medical_history, monitoring, scientific_references,
--          treatment_plans
--   003 -> anamnesis_reports
--
-- Nao tocamos em colunas TIMESTAMPTZ ja corretas (definidas em migrations
-- 004+). Nao tocamos em `incoming_messages.timestamp` (VARCHAR, fora de
-- escopo desta padronizacao).
--
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Pre-step: drop views que dependem das colunas a converter. Recriamos ao
-- final. Descoberto em 2026-04-19 ao aplicar em Postgres local: a view
-- `clinic_members` (criada em 014) referencia `user_clinics.created_at` e
-- impede o ALTER COLUMN TYPE. Idempotente via IF EXISTS.
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS clinic_members;


-- ---------------------------------------------------------------------------
-- Helper: converte uma coluna TIMESTAMP -> TIMESTAMPTZ somente se o tipo
-- atual ainda for "timestamp without time zone". Idempotente.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    targets CONSTANT TEXT[][] := ARRAY[
        ['clinics',               'created_at'],
        ['clinics',               'updated_at'],
        ['patients',              'created_at'],
        ['ai_prompt_versions',    'created_at'],
        ['users',                 'created_at'],
        ['user_clinics',          'created_at'],
        ['appointments',          'appointment_date'],
        ['appointments',          'created_at'],
        ['message_status_updates','created_at'],
        ['ai_audit_logs',         'created_at'],
        ['alerts',                'alert_time'],
        ['alerts',                'created_at'],
        ['medical_history',       'created_at'],
        ['monitoring',            'created_at'],
        ['scientific_references', 'created_at'],
        ['treatment_plans',       'created_at'],
        ['anamnesis_reports',     'created_at'],
        ['anamnesis_reports',     'updated_at']
    ];
    t TEXT;
    c TEXT;
    current_type TEXT;
BEGIN
    FOR i IN 1 .. array_length(targets, 1) LOOP
        t := targets[i][1];
        c := targets[i][2];

        -- Pula se a tabela nao existir (ambientes parciais)
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
             WHERE table_schema = 'public' AND table_name = t
        ) THEN
            RAISE NOTICE 'skip: tabela % nao existe', t;
            CONTINUE;
        END IF;

        -- Pula se a coluna nao existir
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = t AND column_name = c
        ) THEN
            RAISE NOTICE 'skip: % nao tem coluna %', t, c;
            CONTINUE;
        END IF;

        -- Tipo atual
        SELECT data_type
          INTO current_type
          FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = t
           AND column_name = c;

        IF current_type = 'timestamp with time zone' THEN
            RAISE NOTICE 'ok (ja tztz): %.%', t, c;
        ELSIF current_type = 'timestamp without time zone' THEN
            EXECUTE format(
                'ALTER TABLE %I ALTER COLUMN %I TYPE TIMESTAMPTZ USING %I AT TIME ZONE ''UTC''',
                t, c, c
            );
            RAISE NOTICE 'converted: %.% -> TIMESTAMPTZ', t, c;
        ELSE
            RAISE WARNING 'tipo inesperado para %.%: %', t, c, current_type;
        END IF;
    END LOOP;
END
$$;


-- ---------------------------------------------------------------------------
-- Normalizar defaults: garantir que os defaults das colunas convertidas
-- continuem usando NOW() (retrocompatibilidade plena com CURRENT_TIMESTAMP,
-- mas alinha com o padrao adotado nas migrations mais recentes).
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    defaults CONSTANT TEXT[][] := ARRAY[
        ['clinics',               'created_at'],
        ['clinics',               'updated_at'],
        ['patients',              'created_at'],
        ['ai_prompt_versions',    'created_at'],
        ['users',                 'created_at'],
        ['user_clinics',          'created_at'],
        ['appointments',          'created_at'],
        ['message_status_updates','created_at'],
        ['ai_audit_logs',         'created_at'],
        ['alerts',                'alert_time'],
        ['alerts',                'created_at'],
        ['medical_history',       'created_at'],
        ['monitoring',            'created_at'],
        ['scientific_references', 'created_at'],
        ['treatment_plans',       'created_at'],
        ['anamnesis_reports',     'created_at'],
        ['anamnesis_reports',     'updated_at']
    ];
    t TEXT;
    c TEXT;
BEGIN
    FOR i IN 1 .. array_length(defaults, 1) LOOP
        t := defaults[i][1];
        c := defaults[i][2];

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = t AND column_name = c
        ) THEN
            CONTINUE;
        END IF;

        EXECUTE format(
            'ALTER TABLE %I ALTER COLUMN %I SET DEFAULT NOW()',
            t, c
        );
    END LOOP;
END
$$;


-- ---------------------------------------------------------------------------
-- Recria a view clinic_members que foi dropada no pre-step. Definicao
-- identica a 014_missing_tables_and_columns.sql.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW clinic_members AS
SELECT user_id, clinic_id, role AS clinic_role, is_default, created_at
FROM user_clinics;


-- ============================================================================
-- Fim da migration 023. O runner registra a versao e o checksum em
-- schema_migrations; nao e necessario INSERT manual aqui.
-- ============================================================================
