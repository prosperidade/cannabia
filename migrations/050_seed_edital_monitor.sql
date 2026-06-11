-- migrations/050_seed_edital_monitor.sql
-- SCC-2 / A6 (doc 30 Onda 1): vigilancia do EDITAL do sandbox regulatorio.
--
-- A RDC 1.014/2026 cria o sandbox regulatorio para associacoes, mas a
-- implementacao depende de um EDITAL proprio, ainda SEM DATA (ver MEMORIA_VIVA
-- §2 e docs/29.5). Esta migration REUSA a infra existente de knowledge_monitors
-- (migration 017) para vigiar as fontes oficiais (Anvisa e DOU) em busca da
-- publicacao desse edital.
--
-- FRAMING (fixado por Andre, doc 30 v1.1): a vigilancia e COMERCIAL — a CannabIA
-- nao e proponente nem tem prazo/obrigacao com a Anvisa; o objetivo e avisar as
-- ASSOCIACOES CLIENTES primeiro (vantagem do plano "Sandbox Ready"). Quem
-- submete/concorre ao edital e cada associacao, por decisao propria (P1).
--
-- Deteccao e ingestao reusam o AgenteExtrator (_check_monitor/_run_all_monitors,
-- src/ai/agents/extrator.py) e a superficie admin reusa GET de monitores em
-- src/web/routes/knowledge.py (list_monitors). Notificacao ATIVA (push/e-mail)
-- ao admin e follow-up (depende da camada de notificacao — doc 30 Onda 2/3).
--
-- Idempotente: INSERT guardado por NOT EXISTS no `name`. Down remove os 2 seeds.
-- ============================================================================

-- Monitor 1 — DOU (Imprensa Nacional): busca pelo edital do sandbox.
INSERT INTO knowledge_monitors (name, url, source_type, search_query, check_interval_hours, max_items, is_active)
SELECT
    'EDITAL Sandbox RDC 1.014 — DOU (vigilancia comercial)',
    'https://www.in.gov.br/consulta',
    'dou',
    'edital chamamento sandbox regulatorio RDC 1.014 associacoes cannabis',
    12,
    10,
    TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM knowledge_monitors
    WHERE name = 'EDITAL Sandbox RDC 1.014 — DOU (vigilancia comercial)'
);

-- Monitor 2 — Portal Anvisa: pagina do sandbox/associacoes.
INSERT INTO knowledge_monitors (name, url, source_type, search_query, check_interval_hours, max_items, is_active)
SELECT
    'EDITAL Sandbox RDC 1.014 — Anvisa (vigilancia comercial)',
    'https://www.gov.br/anvisa/pt-br/assuntos/regulamentacao/legislacao/resolucoes-da-diretoria-colegiada',
    'anvisa',
    'edital sandbox regulatorio associacoes RDC 1.014',
    12,
    10,
    TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM knowledge_monitors
    WHERE name = 'EDITAL Sandbox RDC 1.014 — Anvisa (vigilancia comercial)'
);
