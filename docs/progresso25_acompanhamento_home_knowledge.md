# Progresso 25 — P2 + P3 + P1 da Fase A2 (acompanhamento, home dinâmica, base científica global)

**Data:** 2026-04-27
**Branch:** `main`
**Commits da sessão:** `95ec31c`, `dfb72a5`, `85d1f4a`, `6611321` (todos pushed para `origin/main`)
**Suite:** 1321 passed + 185 skipped (era 1273 + 185 antes), 0 falhas
**Type-check frontend:** zero erros

## 1. Contexto de entrada

Estado herdado do progresso24 (2026-04-26):
- SCC dev puro 100% fechado (commit `81671c4`)
- Fase A2 começou — roles refinadas com `is_clinic_admin`, sidebar dinâmico via `lib/nav.ts`, `/org/configuracoes` com 6 abas, `/org/acompanhamento` skeleton
- Suite em 1458 (1273 passed + 185 skipped)
- Pendências priorizadas: P1 (base científica), P2 (KPIs em acompanhamento), P3 (home por role)

Decisão do usuário no início da sessão: **executar P2 → P3 → P1 nessa ordem**, com commit a cada fase, suite verde sempre.

## 2. P2 — KPIs reais em /org/acompanhamento

**Commit:** `95ec31c`

### Problema
A tela `/org/acompanhamento` foi entregue na Fase A2 como skeleton: 4 cards de KPI mostrando `—`, faixa de "atividade dos agentes" sem dados, e listagem de pacientes em "Em construção".

### Decisões de schema
Mapeamento das fontes:
- `adverse_events` (migration 031) — tem `tenant_id` direto
- `scheduled_followups` (migration 013) — usa `clinic_id`, JOIN em `clinics.tenant_id`
- `triage_links` (migration 018) — usa `clinic_id`, JOIN em `clinics.tenant_id`
- `ai_audit_logs` (migration 001) — usa `clinic_id`, JOIN em `clinics.tenant_id`

### Implementação

**Arquivos novos:**
- `src/repositories/acompanhamento_repository.py` — 5 funções de leitura agregada (4 KPIs + atividade dos agentes)
- `src/services/acompanhamento_service.py` — `get_overview(tenant_id) -> AcompanhamentoOverview` com `KpiSnapshot` + tupla fixa de 4 `AgentActivity` (Triagem/Anamnese/FollowUp/Regulatorio)
- `src/web/routes/acompanhamento.py` — blueprint `GET /api/v1/org/acompanhamento/overview`, roles `Admin/AdminClinica/Medico/Recepcao`
- `tests/test_acompanhamento_service.py` — 24 testes (classificação por substring + agregação + KPIs)
- `tests/test_acompanhamento_routes.py` — 9 testes (4 roles allow + 2 deny + 401 + 400 + clinic_id fallback)

**Arquivos modificados:**
- `src/app.py` — registra `acompanhamento_bp`
- `frontend/lib/api.ts` — `getAcompanhamentoOverview()` + tipos
- `frontend/app/org/acompanhamento/page.tsx` — fetch real, loading/error, badge "N ações / 24h", timestamp formatado

### Definições dos KPIs (registradas no código)

| KPI | Query |
|-----|-------|
| `patients_at_risk` | `adverse_events` WHERE tenant_id=$1 AND severity IN ('severe','life_threatening') AND clinical_assessment IS NULL |
| `adverse_events_open` | `adverse_events` WHERE tenant_id=$1 AND outcome IS NULL |
| `followups_pending` | `scheduled_followups sf` JOIN `clinics c` WHERE c.tenant_id=$1 AND sf.responded_at IS NULL AND sf.status IN ('pending','sent') |
| `triages_in_progress` | `triage_links tl` JOIN `clinics c` WHERE c.tenant_id=$1 AND tl.status='active' AND tl.used_at IS NULL AND tl.expires_at > NOW() |

`triages_in_progress` é aproximação até P5 trazer o agente Triagem dedicado — comentado no código.

### Atividade dos agentes (24h)

Classificação por substring no `endpoint` registrado em `ai_audit_logs`:
- `triage|triagem` → Triagem
- `anamnes|intake|conversation` → Anamnese
- `follow` → FollowUp
- `regulator|vigimed|pharmacovigil|anvisa|notivisa` → Regulatorio

Endpoints fora do mapa são ignorados. A saída sempre tem os 4 agentes em ordem fixa, com `actions=0` quando não houve atividade.

## 3. P3 — Home dinâmica por role

**Commit:** `dfb72a5`

### Estado herdado
- `/admin` — super-admin global (já específico)
- `/org/dashboard` — Painel Gerencial com KPIs/charts/top médicos (Dono e AdminClinica). Mockado em parte mas estrutura adequada
- `/org/acompanhamento` — Recepção (já vai pra cá pelo getRoleRedirect, e já tem KPIs reais após P2)
- `/med/dashboard` — Médico puro. **Conteúdo errado**: mostrava "Inteligência Botânica" de paciente único + status físico/emocional, não fila do dia
- Pacientes não foram trabalhados nesta sessão (decisão do usuário)

### Mudanças

**`/med/dashboard` reescrito:**
- 3 KPIs reais: em fila agora, atendidos hoje, retornos pendentes (filtrados client-side a partir de `listAppointments()` e `listReturns()`)
- Card **Fila do dia** com lista compacta dos appointments de hoje (top 8 + paginação)
- Card **Retornos pendentes** com top 5
- Header "Olá, {username}" + data atual em PT-BR
- Removidas seções mock de paciente único

**`/org/acompanhamento` ganha "Agenda de hoje":**
- Card adicional no topo, antes dos alertas
- Lista appointments de hoje filtrados client-side
- Mantém os KPIs e atividade dos agentes da P2

**`/org/dashboard` (Dono / AdminClinica):**
- Não alterado. Já é "KPIs gerais" como o briefing pediu. Plugar dados reais é trabalho de outra sprint.

### Nota técnica
Status de appointment é heurística client-side:
- "Em fila" = `agendado/confirmado/pending/scheduled`
- "Atendido" = `atendido/completed/finalizado/concluido`

Se for definir status canônico no backend, vira outra task. Hoje cada caller usa o que quer.

## 4. P1 — Base científica global colaborativa

**Commit:** `85d1f4a` (refinamento de backlog em `6611321`)

### Investigação que mudou o plano

Inicialmente eu havia proposto "escopar a base por tenant_id". O usuário corrigiu: **a base é GLOBAL e COLABORATIVA**. Todos os profissionais credenciados leem e adicionam num pool compartilhado. Os agentes IA, conforme processam casos, também devem alimentar essa base.

Investigação no código revelou o estado real:

| Aspecto | Estado anterior | Após P1 |
|---------|-----------------|---------|
| `clinic_id` em `knowledge_catalog`/`knowledge_monitors` | Coluna existia (`DEFAULT 1`) mas nenhuma query filtrava por ela — campo morto que dava falsa sensação de multi-tenant | Removida (migration 040) |
| Autoria | Não existia | `created_by INT REFERENCES users(id)` (migration 040) |
| Roles que leem | Apenas `Admin` + `Medico` | `Admin` + `AdminClinica` + `Medico` (Recepção/Financeiro/Paciente bloqueados — decisão do usuário: base é curatorial-científica) |
| Roles que adicionam | Mesmo conjunto | Mesmo conjunto |
| Gestão de monitors | Apenas `Admin` | `Admin` + `AdminClinica` |
| DELETE | Não existia rota | Nova rota com regra de autoria: Admin global deleta qualquer; demais só o que adicionaram |
| `/org/conhecimento` | Placeholder com link "Acessar versão do super admin" | UI funcional via componente compartilhado |

### Migration 040

Arquivo: `migrations/040_knowledge_global_authorship.sql` (+ `down/`)

```sql
-- knowledge_catalog
ADD COLUMN created_by INT
ADD CONSTRAINT fk_knowledge_catalog_created_by FOREIGN KEY (created_by) REFERENCES users(id)
CREATE INDEX idx_knowledge_catalog_created_by ON knowledge_catalog (created_by)
DROP COLUMN IF EXISTS clinic_id

-- knowledge_monitors (idem)
```

Aplicada no DB local Docker (`cannabia-postgis`) na sessão. Pendente de aplicar em qualquer outro ambiente antes de subir backend.

### Backend

**`src/web/routes/knowledge.py` — reescrito:**
- Helpers locais `_current_user_id()`, `_is_admin_global()`, `_can_delete(created_by)`
- Roles ampliadas em todas as rotas
- INSERT em `knowledge_monitors` agora grava `created_by`
- Novas rotas: `DELETE /catalog/<id>` e `DELETE /monitors/<id>` com regra de autoria

**`src/ai/agents/extrator.py`:**
- INSERT em `knowledge_catalog` removeu `clinic_id` e adicionou `created_by`
- `_auto_search_and_ingest` aceita `created_by` via kwargs e injeta nos `doc_data` (PubMed + legislação)
- `execute()` para `auto_search` propaga `created_by` via `invoke_skill`

**`src/knowledge/legislation_catalog.py`:**
- `_build_catalog_record` e `sync_legislation_catalog` substituíram parâmetro `clinic_id` por `created_by`
- INSERT e UPDATE atualizados (sem `clinic_id`, com `created_by`)

**`src/web/routes/regulatory.py`:**
- Caller de `sync_legislation_catalog` agora passa `created_by` do user logado
- Removidas as importações `g, request` que ficaram não-usadas

### Frontend

**Novo componente: `frontend/components/knowledge/knowledge-base-view.tsx`** — UI compartilhada com:
- Busca textual + filtro por `doc_type`
- Card "Adicionar via PubMed" que dispara `triggerAutoSearch` com termo escolhido
- Lista de itens com expand/collapse
- Botão DELETE só renderiza se `canDelete(item)` (autoria ou Admin global)

**`frontend/app/org/conhecimento/page.tsx`** — agora apenas renderiza `<KnowledgeBaseView />`

**`frontend/app/med/conhecimento/page.tsx`** — mantido como redirect para `/org/conhecimento` (já era assim)

**`frontend/app/admin/knowledge/page.tsx`** — **não alterado.** Decisão do usuário: o `/admin/knowledge` continua sendo a versão "power user" com gestão de monitors completa.

### Tests

- `tests/test_knowledge_routes.py` — reescrito com 21 testes (lista catalog, stats, monitors com created_by, DELETE com autoria por role: Admin/AdminClinica/Medico/Recepcao bloqueada, 404 quando ausente, mesma regra para monitors)
- `tests/test_legislation_catalog.py` — ajustado para nova assinatura (parâmetro `created_by` em vez de `clinic_id`)
- `tests/test_regulatory_routes.py` — lambda do mock atualizado para nova assinatura

### Decisões registradas em código (não revisitar)

1. **Base é global, não escopada por tenant.** `clinic_id` foi removido. Todos os tenants credenciados compartilham o pool.
2. **Recepção, Financeiro e Paciente NÃO acessam.** Decisão explícita: a base é curatorial-científica.
3. **DELETE com autoria.** Admin global deleta qualquer; AdminClinica e Medico só o que eles mesmos adicionaram. Implementação via `created_by` + helper `_can_delete()`.
4. **`/admin/knowledge` continua sendo a UI super-admin.** O componente compartilhado é uma versão focada para `/org` e `/med`.

## 5. C6 e C7 — dívidas técnicas registradas

**Commit:** `6611321`

Após investigação no `cientifico.py`, ficou claro que o que o usuário descreveu como "agentes adicionando à base conforme processam casos" são na verdade **dois fluxos com naturezas técnicas distintas**, e nenhum dos dois está implementado hoje:

### C6 — agentes ingerindo o que pesquisam durante atendimento

**Estado hoje:** O `AgenteCientifico` em [src/ai/agents/cientifico.py](src/ai/agents/cientifico.py) apenas CONSOME ChromaDB via `_search_evidence`. Quando a query traz 0 chunks, ele só roda o relatório em fallback sem RAG (`run_scientific_report` em vez de `run_scientific_report_rag`). Não busca PubMed em tempo real, não adiciona nada na base. Quem busca PubMed e adiciona é só o `AgenteExtrator`, e por trigger MANUAL via `POST /api/v1/knowledge/auto-search`.

**Trabalho:** helper `register_to_knowledge_base()` no `BaseAgent` + gancho no `AgenteCientifico` (e em qualquer agente que faça consulta externa) para registrar artigo encontrado durante o atendimento. Política de qualidade leve. Executável rápido.

### C7 — extração de conhecimento clínico agregado

**Estado hoje:** Os agentes Anamnese/Tratamento/Prescritor já gravam dados estruturados em `medical_history`, `treatment_plans`, `anamnesis_reports`, `adverse_events`, `dispensations`, `prescriptions` — mas isolados por paciente. Não existe pipeline que agregue achados longitudinais (ex.: "neste recorte, CBD 5mg + THC 0.5mg foi eficaz em 80% das epilepsias refratárias", padrões de combinação, eventos adversos correlacionados a cepa) em material indexável na `knowledge_catalog`.

**Trabalho:** sprint dedicada — pipeline periódico (cron), anonimização LGPD, schema de "caso clínico" no `knowledge_catalog`, curadoria.

Os dois ficaram registrados na **Frente C** do [docs/22_EXECUTIVE_BACKLOG.md](docs/22_EXECUTIVE_BACKLOG.md) com Status `Aberto` e Prioridade `Alta`.

## 6. Decisão estratégica do usuário sobre P5

P5 (refatorar agentes IA um por um — prompts, skills, tools) **fica como última passada**, depois de fechar todas as outras pendências e dívidas. Razão: quando entrarmos nos agentes individualmente, todo o resto do produto já estará estável e os requisitos (incluindo C6/C7) vão estar claros, evitando refatorar agentes várias vezes.

## 7. Roadmap atualizado

Em ordem de execução:

| # | Item | Tamanho |
|---|------|---------|
| 1 | App paciente (bug envelope `/patient/profile` + telas `/p/documentos` e `/p/consultas`) | médio |
| 2 | C6 — agentes ingerindo o que pesquisam no atendimento | pequeno |
| 3 | C7 — agregação de conhecimento clínico dos casos (LGPD + pipeline + schema novo) | sprint dedicada |
| 4 | `/org/dashboard` com dados reais (atualmente parte mockada) | pequeno |
| 5 | `/org/acompanhamento` listagem de pacientes em acompanhamento ativo | pequeno |
| 6 | **P5 — última passada** — refatorar agentes IA um por um | longo |

**Próxima sessão:** começar pelo app paciente (item 1).

## 8. Pendências operacionais (ops/deploy, não dev — inalteradas)

- **Anchoring:** deploy `SandboxAnchor.sol` Polygon Amoy, web3+OTS instalados, `_ProductionPolygonClient` / `_ProductionOtsClient` plugados, cron upgrade, multi-sig mainnet
- **Pharmacovigilance:** creds ANVISA, `_ProductionVigiMedClient` / `_ProductionNotivisaClient` plugados, env var em prod
- **Encriptação:** `tenant_settings` JSONB tem chaves sensíveis em texto plano em DEV; sprint dedicada de `tenant_secrets` criptografados antes de PROD
- **Migration 040:** aplicada apenas no DB local desta máquina. Aplicar em outros ambientes antes de subir backend lá.

## 9. Suite

```
1321 passed, 185 skipped in 67.57s
```

Antes da sessão: 1273 passed + 185 skipped (1458 total).
Após P2: +33 testes (1306 passed).
Após P3: zero novos testes (mudança visual).
Após P1: +15 testes (1321 passed).

Type-check frontend zero erros em todas as fases.
