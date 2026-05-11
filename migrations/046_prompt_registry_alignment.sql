-- Migration 046: Reconciliacao do schema drift entre prompt_registry.py e
-- ai_prompt_versions (criada em 001_initial_schema.sql).
--
-- Sprint 2 Track Reg — Q3=b da Sprint 1 fechado (adiamento aprovado).
--
-- Achado do Phase 0: src/ai/prompt_registry.py (317 linhas) JA estava 100%
-- implementado, mas usava colunas `prompt_key` e `is_active` enquanto a
-- migration 001 criou `name` e `active`. Resultado: o load_from_db() falhava
-- silenciosamente (log em DEBUG, ninguem viu) e o registry SEMPRE caiu no
-- fallback hardcoded — DB-first NUNCA ATIVOU em producao.
--
-- Estrategia: ALTER TABLE adicionando colunas que o registry espera,
-- mantendo as antigas para compat. `is_active` vira GENERATED ALWAYS AS
-- (active) STORED — alias automatico, sem trigger, sem app code mudando.
-- Backfill `prompt_key = name` em registros existentes (zero hoje, mas
-- defensivo se alguem rodou seed manual).

ALTER TABLE ai_prompt_versions ADD COLUMN IF NOT EXISTS prompt_key VARCHAR(50);
ALTER TABLE ai_prompt_versions ADD COLUMN IF NOT EXISTS is_active BOOLEAN GENERATED ALWAYS AS (active) STORED;
ALTER TABLE ai_prompt_versions ADD COLUMN IF NOT EXISTS created_by VARCHAR(100);
ALTER TABLE ai_prompt_versions ADD COLUMN IF NOT EXISTS model VARCHAR(50);
ALTER TABLE ai_prompt_versions ADD COLUMN IF NOT EXISTS agent_name VARCHAR(50);

UPDATE ai_prompt_versions SET prompt_key = name WHERE prompt_key IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_prompt_versions_key_version
  ON ai_prompt_versions(prompt_key, version);

COMMENT ON COLUMN ai_prompt_versions.prompt_key  IS 'Sprint 2 Track Reg: alinhamento com prompt_registry.py';
COMMENT ON COLUMN ai_prompt_versions.is_active   IS 'Sprint 2 Track Reg: alias generated de active';
COMMENT ON COLUMN ai_prompt_versions.created_by  IS 'Sprint 2 Track Reg: user_id de quem criou (admin UI)';
COMMENT ON COLUMN ai_prompt_versions.model       IS 'Sprint 2 Track Reg: modelo alvo do prompt (gpt-4o-mini etc)';
COMMENT ON COLUMN ai_prompt_versions.agent_name  IS 'Sprint 2 Track Reg: agente que consome o prompt';
