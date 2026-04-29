# Progresso 26 — C6 fechada: agentes ingerindo PubMed durante atendimento

**Data:** 2026-04-29
**Branch:** `main`
**Suite:** 1345 passed + 185 skipped (era 1321 + 185), 0 falhas
**Type-check frontend:** sem alteração — esta sprint é 100% backend

## 1. Contexto

A sessão de 2026-04-27 (progresso25) deixou registrado em `docs/22_EXECUTIVE_BACKLOG.md` que a base científica colaborativa estava "metade pronta": o RAG **lia** mas a base não **crescia** com o uso real do produto. Os dois gaps:

- **C6** — agentes ingerindo PubMed em tempo real durante atendimento
- **C7** — agregação de conhecimento clínico longitudinal (sprint dedicada futura)

O usuário escolheu seguir a sugestão de começar pela C6 hoje (rápida, fecha dívida da Frente C, encadeia bem com a P1 da sessão anterior).

## 2. Estado anterior (problema concreto)

`AgenteCientifico` ([src/ai/agents/cientifico.py](src/ai/agents/cientifico.py)) só consumia ChromaDB via `_search_evidence`. Quando a query trazia 0 chunks, caía em `run_scientific_report` (LLM sem RAG) e nada novo entrava na base. O único caminho de crescimento era o `AgenteExtrator` via trigger manual `POST /api/v1/knowledge/auto-search` — não acionado pelo fluxo de atendimento.

Resultado: o "diferencial RAG" anunciado em [CLAUDE.md](CLAUDE.md) ("base cresce com os casos") era retórico.

## 3. Implementação

### 3.1. Helper compartilhado de catálogo

**Novo: [src/knowledge/auto_ingest.py](src/knowledge/auto_ingest.py)**

- `register_article_in_catalog(doc_data: dict) -> dict`: extraído do `AgenteExtrator._register_in_catalog`. Faz INSERT em `knowledge_catalog` com dedup por DOI e por `source_url`. Retorna `{registered, catalog_id, reason, error?}`.
- `is_quality_acceptable(article: dict) -> bool`: política leve de curadoria para o gancho automático durante atendimento. Aceita se:
  - título com ≥ 20 caracteres
  - abstract com ≥ 80 caracteres
  - ao menos um identificador externo (DOI ou source_url)

A política é deliberadamente leve. Itens fora dos mínimos não entram pelo caminho automático — se forem relevantes, o curador adiciona via fluxo manual (`/admin/knowledge` ou `/org/conhecimento`).

### 3.2. Cliente PubMed standalone

**Novo: [src/knowledge/pubmed.py](src/knowledge/pubmed.py)**

- `search_pubmed_articles(query, max_results)` — esearch + esummary
- `fetch_pubmed_abstract(pmid)` — efetch
- `parse_pubmed_date(raw)` — normaliza para ISO

Extraído do `AgenteExtrator` para evitar acoplamento entre agentes (cientifico → extrator). Single source of truth para PubMed E-utilities.

### 3.3. BaseAgent ganha `register_to_knowledge_base()`

**Modificado: [src/ai/agents/base.py](src/ai/agents/base.py)**

```python
def register_to_knowledge_base(
    self,
    doc_data: Dict[str, Any],
    created_by: Optional[int] = None,
) -> Dict[str, Any]:
```

Wrapper fire-and-forget sobre `register_article_in_catalog`. Marca `ingested_by = "agent_<nome>_auto"` automaticamente (a menos que o caller forneça explícito), propaga `created_by`, e nunca levanta exceção (retorna `{"registered": False, "reason": "exception", "error": "..."}` em caso de falha de import/runtime).

Disponível para qualquer agente futuro que faça consulta externa (Tratamento, Anamnese, Regulatório, etc.).

### 3.4. AgenteCientifico — gancho C6

**Modificado: [src/ai/agents/cientifico.py](src/ai/agents/cientifico.py)**

Mudanças no `execute()`:

1. `_build_query(treatment_plan, kwargs)` — método estático novo. Prioridade:
   1. `kwargs["_memory_context"].query` (já preenchido pelo `clinical_flow.py` linha 68 com `main_complaint | cannabinoid_ratio`)
   2. concat dos campos texto do TreatmentPlan (`cannabinoid_ratio + administration_route + monitoring_plan`)
   3. fallback para JSON do plan truncado a 500 chars
   Substituiu o `json.dumps(treatment_plan)` que era usado como query de RAG e gerava lixo.
2. Quando `_search_evidence` retorna 0 chunks **e** `auto_ingest_evidence != False`:
   - Aciona nova skill `auto_ingest_evidence`
   - Se a skill ingere ≥ 1 chunk no ChromaDB, **re-roda** `_search_evidence` para que a chamada atual já use RAG
   - Caso contrário, segue para fallback non-RAG normalmente

Skill nova `auto_ingest_evidence(query_text, max_results=3, created_by=None)`:

- Busca PubMed top 3 (parâmetro configurável via `kwargs["auto_ingest_max"]`)
- Para cada artigo: fetch abstract → filtro `is_quality_acceptable` → registra no catálogo via `self.register_to_knowledge_base()`
- Se registrou (não é duplicate): embeda o abstract e adiciona como chunk único no ChromaDB com metadata `ingested_by = agent_cientifico_auto` + `catalog_id`
- Respeita rate limit do PubMed (sleep 0.4s por artigo)

A flag `auto_ingest_evidence=False` no kwargs do `execute()` desabilita o gancho — útil para testes e contextos batch onde RAG miss é aceitável.

### 3.5. AgenteExtrator delega ao helper compartilhado

**Modificado: [src/ai/agents/extrator.py](src/ai/agents/extrator.py)**

`_register_in_catalog` reduzido a 5 linhas que importam e chamam `register_article_in_catalog`. Comportamento preservado — comprovado pela suite que mantém zero regressão no caminho `auto_search` manual.

## 4. Testes

24 testes novos, todos passando:

**[tests/test_auto_ingest.py](tests/test_auto_ingest.py) — 9 testes**

- `register_article_in_catalog`: insert OK, dedup por DOI, dedup por URL, db_error não sobe
- `is_quality_acceptable`: aceita completo, rejeita título curto, rejeita abstract curto, rejeita sem identificador, aceita só com URL

**[tests/test_base_agent_knowledge.py](tests/test_base_agent_knowledge.py) — 5 testes**

- `ingested_by` recebe sufixo `_auto` automaticamente
- `ingested_by` explícito do caller é preservado
- `created_by` propagado para o payload
- Exception no helper compartilhado vira retorno `{registered: False, reason: "exception"}`
- Resposta de dedup atravessa intacta

**[tests/test_cientifico_auto_ingest.py](tests/test_cientifico_auto_ingest.py) — 10 testes**

- `_build_query`: prefere `_memory_context.query`, cai para campos do plan, default seguro com plan vazio
- `execute`: pula auto-ingest quando há chunks; dispara auto-ingest quando vazio + re-busca; respeita `auto_ingest_evidence=False`; segue para fallback quando PubMed retorna nada
- skill `_auto_ingest_evidence`: filtra por qualidade e ingere só os bons; pula ChromaDB para duplicatas; retorna zeros quando PubMed vazio

### 4.1. Pegadinha técnica do BaseAgent

`BaseAgent.invoke_skill(name)` resolve o handler a partir de `self._skills[name].handler`, capturado em `__init__` como **bound method**. Isso significa que `patch.object(agent, "_search_evidence", ...)` em testes **não surte efeito** — a referência guardada no skill registry continua apontando para o método original.

Solução nos testes: helper `_patch_skills(agent, **handlers)` que faz `patch.object(skill, "handler", mock)` no objeto `Skill`. Documentado no docstring do helper para futuras sprints que mockam skills.

## 5. Decisões de produto registradas

1. **Limite de 3 artigos por chamada de auto-ingest** (configurável via `auto_ingest_max`). Justificativa: o caminho lento (RAG miss) já carrega o custo de LLM call de vários segundos; +3 PubMed requests + 3 embeddings adiciona ~2s e é aceitável. Mais que isso vira sobrecarga.
2. **Re-search do ChromaDB pós-ingest, no mesmo call.** Para que a própria chamada que descobriu o gap use RAG real — não apenas as próximas. Custo: 1 query extra ao ChromaDB (~300ms). Valor: a primeira clínica a investigar uma condição rara já se beneficia.
3. **Política leve em vez de pesada.** Não verificamos relevância semântica do artigo, autoria de jornal, peer-review status. Apenas estrutura mínima (título/abstract/identificador). Curadoria pesada fica para o futuro `/admin/knowledge` quando o volume crescer e a métrica de "lixo na base" virar dor.
4. **`created_by` opcional.** Quando `clinical_flow.py` invoca o cientifico, hoje não passa `created_by`. O artigo entra com `created_by = NULL` (ingestão anônima automática). Se quisermos atribuir ao médico do atendimento, basta `clinical_flow.py` passar `created_by=user_id` no `cientifico.run(...)`. Não fiz nessa sprint para manter escopo apertado.

## 6. Roadmap atualizado

| # | Item | Tamanho | Estado |
|---|------|---------|--------|
| 1 | App paciente (bug envelope `/patient/profile` + telas `/p/documentos` e `/p/consultas`) | médio | Pendente |
| ~~2~~ | ~~C6 — agentes ingerindo o que pesquisam no atendimento~~ | ~~pequeno~~ | **Concluída 2026-04-29** |
| 3 | C7 — agregação de conhecimento clínico dos casos (LGPD + pipeline + schema novo) | sprint dedicada | Pendente |
| 4 | `/org/dashboard` com dados reais (atualmente parte mockada) | pequeno | Pendente |
| 5 | `/org/acompanhamento` listagem de pacientes em acompanhamento ativo | pequeno | Pendente |
| 6 | **P5 — última passada** — refatorar agentes IA um por um | longo | Pendente |

**Próxima sessão (sugestão):** seguir para o **app paciente** conforme decidido em 2026-04-27, ou intercalar pequenos (#4 e #5) primeiro para acumular momentum antes da sprint dedicada da C7.

## 7. Pendências operacionais (inalteradas)

- Anchoring Polygon Amoy + multi-sig mainnet
- Pharmacovigilance ANVISA
- Encriptação `tenant_secrets` antes de PROD
- Migration 040 em outros ambientes
