-- Down migration 026: reverter Members Schema
--
-- Reverte a criacao das duas tabelas do dominio `members` aplicadas pela
-- up-migration 026_members_schema.sql.
--
-- ATENCAO — perda informacional:
--
-- Dropar `association_members` e `member_consents` **descarta** todos os
-- registros de vinculos associativos e historico de consentimentos. Em
-- ambiente com dados reais isso tem implicacoes de LGPD (consentimento e
-- prova legal obrigatoria) — o caminho oficial para voltar a um estado
-- anterior com dados e restore por backup, ver
-- docs/BACKUP_AND_DISASTER_RECOVERY.md §4.
--
-- `tenants`, `patients`, `prescriptions` nao sao tocadas (existiam antes
-- da 026).
--
-- Ordem de drop e INVERSA a ordem de criacao, por causa da FK interna
-- `member_consents.member_id -> association_members.id`:
--
--   member_consents        (dependente)
--   association_members    (referenciada por member_consents)
--
-- Idempotente: todos os DROPs usam IF EXISTS.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Tabelas (em ordem reversa da criacao)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS member_consents;
DROP TABLE IF EXISTS association_members;


-- ============================================================================
-- Fim do down 026. Apos executar, remova manualmente o registro:
--   DELETE FROM schema_migrations WHERE version = '026';
--
-- Indexes, CHECKs e UNIQUE sao dropados em cascata junto com as tabelas.
-- ============================================================================
