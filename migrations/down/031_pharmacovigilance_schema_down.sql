-- Down migration 031: reverter Pharmacovigilance Schema
--
-- Reverte a criacao das 4 tabelas do dominio pharmacovigilance.
--
-- ATENCAO — perda informacional:
--
-- Dropar adverse_events e pharmacovigilance_notifications destroi historico
-- de eventos adversos reportados + notificacoes a Vigimed/NotiVisa. Esse
-- dado e evidencia regulatoria obrigatoria (RDC 406/2020). Em ambiente com
-- dados reais, o caminho oficial e restore por backup — ver
-- docs/BACKUP_AND_DISASTER_RECOVERY.md §4.
--
-- Ordem de drop e INVERSA a ordem de criacao, respeitando FKs:
--
--   risk_controls                    → sanitary_risks
--   pharmacovigilance_notifications  → adverse_events
--   sanitary_risks                   → (sem filhas apos drop de risk_controls)
--   adverse_events                   → (sem filhas apos drop de notifications)
--
-- Idempotente: DROP TABLE IF EXISTS.
-- ============================================================================

DROP TABLE IF EXISTS risk_controls;
DROP TABLE IF EXISTS pharmacovigilance_notifications;
DROP TABLE IF EXISTS sanitary_risks;
DROP TABLE IF EXISTS adverse_events;


-- ============================================================================
-- Fim do down 031. Apos executar, remova manualmente o registro:
--   DELETE FROM schema_migrations WHERE version = '031';
-- ============================================================================
