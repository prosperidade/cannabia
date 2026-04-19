-- Migration 022: Integrity Hardening (P0.1 do docs/BACKLOG_SCC.md)
--
-- Consolida ajustes de integridade identificados na auditoria de
-- docs/progresso17_auditoria_completa_e_melhorias.md e listados como
-- pre-requisitos obrigatorios antes da escrita de qualquer tabela do
-- Sandbox Compliance Core (SCC).
--
-- Escopo:
--   1. UNIQUE case-insensitive em users.email (emails reais, nao NULL/vazio)
--   2. UNIQUE em triage_links.token_hash (remove index nao-unico pre-existente)
--   3. FK em patients.user_id -> users(id) com ON DELETE SET NULL
--   4. CHECK em patients.status (whitelist)
--   5. CHECK em treatment_plans.status (whitelist, permite NULL)
--   6. CHECK em anamnesis_reports.status (whitelist)
--   7. GIN em ai_audit_logs.input_payload
--   8. GIN em ai_audit_logs.output_payload
--
-- Principios:
--   - Idempotente: re-aplicacao nao quebra (IF NOT EXISTS, DO $$ blocks).
--   - Nao-destrutiva: normaliza dados pre-existentes para status conhecidos
--     antes de aplicar CHECK, preservando os valores observados no seed.
--   - Compativel com o runner: nenhum INSERT em schema_migrations embutido
--     (o runner versionado cuida do registro e do checksum).
--
-- ============================================================================

-- ------------------------------------------------------------------------
-- 1. UNIQUE em users.email (case-insensitive, apenas emails populados)
-- ------------------------------------------------------------------------
-- Garante que o mesmo email nao possa ser reutilizado por dois usuarios
-- distintos (independente de capitalizacao), sem bloquear rows antigas
-- com email NULL ou vazio.
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower
    ON users (LOWER(email))
    WHERE email IS NOT NULL AND email <> '';


-- ------------------------------------------------------------------------
-- 2. UNIQUE em triage_links.token_hash
-- ------------------------------------------------------------------------
-- A migration 018 criou `idx_triage_links_token_hash` como indice comum.
-- Promovemos para UNIQUE e removemos o original duplicado.
CREATE UNIQUE INDEX IF NOT EXISTS uq_triage_links_token_hash
    ON triage_links (token_hash);

DROP INDEX IF EXISTS idx_triage_links_token_hash;


-- ------------------------------------------------------------------------
-- 3. FK em patients.user_id -> users(id)
-- ------------------------------------------------------------------------
-- Estabelece relacionamento formal entre paciente e o usuario que o
-- representa no portal. ON DELETE SET NULL mantem o paciente caso o
-- usuario seja apagado (dado clinico permanece; apenas o vinculo se perde).
DO $$
BEGIN
    -- Antes da FK, zerar user_ids que apontam para users inexistentes,
    -- evitando que a FK falhe em ambientes com dados historicos.
    UPDATE patients p
       SET user_id = NULL
     WHERE user_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM users u WHERE u.id = p.user_id);

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
         WHERE constraint_name = 'fk_patients_user'
           AND table_name = 'patients'
    ) THEN
        ALTER TABLE patients
            ADD CONSTRAINT fk_patients_user
            FOREIGN KEY (user_id) REFERENCES users(id)
            ON DELETE SET NULL;
    END IF;
END
$$;


-- ------------------------------------------------------------------------
-- 4. CHECK em patients.status
-- ------------------------------------------------------------------------
-- Whitelist: valores observados no codigo + margem para ciclo de vida
-- operacional (arquivado). Normaliza rows com status NULL ou fora do
-- whitelist para 'ativo' antes de aplicar a constraint.
DO $$
BEGIN
    UPDATE patients
       SET status = 'ativo'
     WHERE status IS NULL
        OR status NOT IN (
            'ativo',
            'inativo',
            'em_tratamento',
            'aguardando_consulta',
            'arquivado'
        );

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
         WHERE constraint_name = 'chk_patients_status'
           AND table_name = 'patients'
    ) THEN
        ALTER TABLE patients
            ADD CONSTRAINT chk_patients_status
            CHECK (status IN (
                'ativo',
                'inativo',
                'em_tratamento',
                'aguardando_consulta',
                'arquivado'
            ));
    END IF;
END
$$;


-- ------------------------------------------------------------------------
-- 5. CHECK em treatment_plans.status (permite NULL para planos pre-014)
-- ------------------------------------------------------------------------
-- Whitelist alinhada ao ciclo de vida de um plano terapeutico: ativo,
-- inativo, suspenso (efeitos adversos), concluido (alta) ou arquivado.
-- NULL permanece valido para rows criadas antes da migration 014 ter
-- adicionado a coluna.
DO $$
BEGIN
    UPDATE treatment_plans
       SET status = 'ativo'
     WHERE status IS NOT NULL
       AND status NOT IN (
            'ativo',
            'inativo',
            'suspenso',
            'concluido',
            'arquivado'
        );

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
         WHERE constraint_name = 'chk_treatment_plans_status'
           AND table_name = 'treatment_plans'
    ) THEN
        ALTER TABLE treatment_plans
            ADD CONSTRAINT chk_treatment_plans_status
            CHECK (
                status IS NULL
             OR status IN (
                    'ativo',
                    'inativo',
                    'suspenso',
                    'concluido',
                    'arquivado'
                )
            );
    END IF;
END
$$;


-- ------------------------------------------------------------------------
-- 6. CHECK em anamnesis_reports.status
-- ------------------------------------------------------------------------
-- Whitelist: valores reais do seed (pendente, revisado) + estados de
-- ciclo de vida previsiveis (arquivado, cancelado). A coluna tem DEFAULT
-- 'pendente' e NOT NULL na definicao original (migration 003), portanto
-- NULL nao precisa ser permitido.
DO $$
BEGIN
    UPDATE anamnesis_reports
       SET status = 'pendente'
     WHERE status IS NULL
        OR status NOT IN (
            'pendente',
            'revisado',
            'arquivado',
            'cancelado'
        );

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
         WHERE constraint_name = 'chk_anamnesis_reports_status'
           AND table_name = 'anamnesis_reports'
    ) THEN
        ALTER TABLE anamnesis_reports
            ADD CONSTRAINT chk_anamnesis_reports_status
            CHECK (status IN (
                'pendente',
                'revisado',
                'arquivado',
                'cancelado'
            ));
    END IF;
END
$$;


-- ------------------------------------------------------------------------
-- 7-8. GIN em ai_audit_logs.input_payload e output_payload
-- ------------------------------------------------------------------------
-- Os payloads JSONB da auditoria sao consultados pelo dashboard com
-- filtros por chave/valor (ex.: modelo usado, paciente, flag clinica).
-- Indices GIN aceleram operadores @>, ? e ?& em JSONB. Ausente ate agora,
-- apontado como risco de degradacao em progresso17.
CREATE INDEX IF NOT EXISTS idx_ai_audit_logs_input_payload_gin
    ON ai_audit_logs USING GIN (input_payload);

CREATE INDEX IF NOT EXISTS idx_ai_audit_logs_output_payload_gin
    ON ai_audit_logs USING GIN (output_payload)
    WHERE output_payload IS NOT NULL;


-- ============================================================================
-- Fim da migration 022. O runner registra a versao e o checksum em
-- schema_migrations; nao e necessario INSERT manual aqui.
-- ============================================================================
