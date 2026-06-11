-- Down de 050_seed_edital_monitor.sql
--
-- Remove os 2 monitores de vigilancia do edital (SCC-2 / A6). Reversao segura:
-- knowledge_monitors e tabela de configuracao operacional; remover os seeds nao
-- afeta dados clinicos nem normas ja ingeridas.
--
-- Apos rodar: DELETE FROM schema_migrations WHERE version = '050';

DELETE FROM knowledge_monitors
 WHERE name IN (
   'EDITAL Sandbox RDC 1.014 — DOU (vigilancia comercial)',
   'EDITAL Sandbox RDC 1.014 — Anvisa (vigilancia comercial)'
 );
