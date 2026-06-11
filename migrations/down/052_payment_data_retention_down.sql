-- Down de 052_payment_data_retention.sql
--
-- Reversao NAO-destrutiva de dados: dropa apenas a tabela de tracking e o
-- indice auxiliar. Nao revive payloads ja expurgados (o expurgo e definitivo,
-- comportamento correto sob LGPD).
--
-- Apos rodar este down, lembre de:
--   DELETE FROM schema_migrations WHERE version = '052';
-- (ver migrations/down/README.md)

DROP INDEX IF EXISTS idx_payment_transactions_received;
DROP TABLE IF EXISTS payment_data_purge_events;
