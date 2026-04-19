-- Down migration 023: reverter timestamp standardization
--
-- Converte 18 colunas TIMESTAMPTZ -> TIMESTAMP (sem fuso), revertendo a
-- up-migration 023_timestamp_standardization.sql.
--
-- ATENCAO — perda informacional:
--
-- A conversao TIMESTAMPTZ -> TIMESTAMP **descarta o fuso-horario**. O
-- procedimento usado aqui normaliza todos os instantes para UTC antes
-- de atribuir o tipo sem fuso (`AT TIME ZONE 'UTC'`), preservando o
-- valor wall-clock em UTC mas removendo a informacao de origem. Se o
-- banco ja tinha dados com fusos locais diferentes misturados, essa
-- perda e irreversivel via SQL.
--
-- Alem disso, drop+recreate da view `clinic_members` e necessario
-- porque ela depende de `user_clinics.created_at` (mesmo motivo da
-- up-migration).
--
-- Idempotente: cada ALTER COLUMN verifica o tipo atual em
-- information_schema antes de converter. Skip de tabelas/colunas
-- ausentes em ambientes parciais.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Pre-step: drop da view que depende de user_clinics.created_at.
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS clinic_members;


-- ---------------------------------------------------------------------------
-- Helper: converte uma coluna TIMESTAMPTZ -> TIMESTAMP somente se o tipo
-- atual for "timestamp with time zone". Idempotente.
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

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
             WHERE table_schema = 'public' AND table_name = t
        ) THEN
            RAISE NOTICE 'skip: tabela % nao existe', t;
            CONTINUE;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = t AND column_name = c
        ) THEN
            RAISE NOTICE 'skip: % nao tem coluna %', t, c;
            CONTINUE;
        END IF;

        SELECT data_type
          INTO current_type
          FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = t
           AND column_name = c;

        IF current_type = 'timestamp without time zone' THEN
            RAISE NOTICE 'ok (ja sem tz): %.%', t, c;
        ELSIF current_type = 'timestamp with time zone' THEN
            EXECUTE format(
                'ALTER TABLE %I ALTER COLUMN %I TYPE TIMESTAMP USING %I AT TIME ZONE ''UTC''',
                t, c, c
            );
            RAISE NOTICE 'reverted: %.% -> TIMESTAMP (UTC wall-clock)', t, c;
        ELSE
            RAISE WARNING 'tipo inesperado para %.%: %', t, c, current_type;
        END IF;
    END LOOP;
END
$$;


-- ---------------------------------------------------------------------------
-- Recria a view clinic_members. Definicao identica a 014 e a recriada
-- pela up-migration 023.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW clinic_members AS
SELECT user_id, clinic_id, role AS clinic_role, is_default, created_at
FROM user_clinics;


-- ============================================================================
-- Fim do down 023. Apos executar, remova manualmente o registro:
--   DELETE FROM schema_migrations WHERE version = '023';
--
-- Nota: os DEFAULTs que a up-migration padronizou para NOW() permanecem
-- apos o revert porque DEFAULT NOW() e sintaticamente valido tanto em
-- TIMESTAMP quanto em TIMESTAMPTZ — so muda a semantica de NOW() no
-- contexto de avaliacao. Nao e necessario resetar.
-- ============================================================================
