-- Down migration 032: reverter Regulatory Schema
--
-- Reverte a criacao das 6 tabelas do dominio regulatory (doc 25 §§9.1-9.3).
--
-- ATENCAO — perda informacional:
--
-- Dropar regulatory_submissions e regulatory_reports destroi evidencia
-- imutavel de submissao (payload_hash) e de relatorios aprovados
-- (content_hash). Esse dado e prova regulatoria enviada a ANVISA no
-- contexto do Sandbox Compliance Core (RDC 660/2022). Em ambiente com
-- dados reais, o caminho oficial e restore por backup — ver
-- docs/BACKUP_AND_DISASTER_RECOVERY.md §4.
--
-- Ordem de drop e INVERSA a ordem de criacao, respeitando FKs:
--
--   regulatory_reports        → sandbox_projects
--   regulatory_submissions    → sandbox_projects
--   sandbox_indicator_values  → sandbox_indicators
--   sandbox_indicators        → sandbox_projects
--   sandbox_protocols         → sandbox_projects
--   sandbox_projects          → (raiz do dominio)
--
-- Idempotente: DROP TABLE IF EXISTS.
-- ============================================================================

DROP TABLE IF EXISTS regulatory_reports;
DROP TABLE IF EXISTS regulatory_submissions;
DROP TABLE IF EXISTS sandbox_indicator_values;
DROP TABLE IF EXISTS sandbox_indicators;
DROP TABLE IF EXISTS sandbox_protocols;
DROP TABLE IF EXISTS sandbox_projects;


-- ============================================================================
-- Fim do down 032. Apos executar, remova manualmente o registro:
--   DELETE FROM schema_migrations WHERE version = '032';
-- ============================================================================
