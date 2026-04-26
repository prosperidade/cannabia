-- Down migration 039 — remove tenant_settings.
-- Atencao: TODOS os campos de configuracao do tenant (cadastro, operacional,
-- integracoes, dna, notificacoes) sao perdidos ao rodar este down. Nao
-- afeta tenant_branding (logo, cores) que esta em tabela separada.
-- ============================================================================

DROP TABLE IF EXISTS tenant_settings;
