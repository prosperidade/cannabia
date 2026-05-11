-- Down de 044_prompt_registry_alignment.sql

DROP INDEX IF EXISTS idx_ai_prompt_versions_key_version;

ALTER TABLE ai_prompt_versions DROP COLUMN IF EXISTS agent_name;
ALTER TABLE ai_prompt_versions DROP COLUMN IF EXISTS model;
ALTER TABLE ai_prompt_versions DROP COLUMN IF EXISTS created_by;
ALTER TABLE ai_prompt_versions DROP COLUMN IF EXISTS is_active;
ALTER TABLE ai_prompt_versions DROP COLUMN IF EXISTS prompt_key;
