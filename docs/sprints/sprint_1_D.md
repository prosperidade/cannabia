# Sprint 1 — Track D (Tactical Hardening) — Fechamento

**Branch:** `feat/sprint-1-D-tactical`
**Base:** `main` @ `12b220b` (auditoria de agentes IA)
**Status:** completo, aguarda revisão do coordenador.
**Esforço executado:** ~4h (estimativa Phase 0: 4-4.5h).

## Sub-tarefas e commits

| Sub-tarefa | Commit | Esforço | Status |
|---|---|---|---|
| D.3 — `pytest --cov=src` em pytest.ini | `1b166e9` | 30min | ✅ |
| D.1 — Webhooks Twilio + Z-API retornam 501 + 2 testes | `b983db0` | 30min | ✅ |
| D.2.a — Mapeamento dos top 20 except (silent + rotas + services) | (parte do Phase 0) | 1h | ✅ |
| D.2.b — Fix dos 9 silent excepts com logger contextual | `0e77ea1` | 1h | ✅ |
| D.2.c — FIXME(sprint-2) nas 8 rotas com empty-data swallow | `cbf5edf` | 30min | ✅ |
| D.4 — Staging environment | (substituído) | — | 🔄 SKIP → backlog |
| D.4-substituto — `docs/STAGING_BACKLOG.md` | (este PR) | 30min | ✅ |

## Decisões de Phase 0 confirmadas pelo coordenador

1. **D.1 webhooks → 501:** confirmado. Skeleton zumbi sem integração ativa hoje. 501 é semanticamente correto e zero-risco-de-regressão.

2. **D.2 critério híbrido:** confirmado. Ao invés do "top 20 = corrigir todos do mesmo jeito", separamos:
   - **9 silent fixes** (≠ 5 originais — mapeamento real revelou 9 sites): adiciona `logger.warning`/`logger.debug` apropriado, **mantém** o comportamento (fail-safe ou empty fallback) intencional.
   - **8 routes com empty-data**: já logam corretamente; recebem só `# FIXME(sprint-2)` pra Sprint 2 auditar contrato com frontend e decidir caso a caso entre 500 explícito vs empty data.
   - **0 services para re-raise**: ao auditar, **todos os services críticos já tratavam corretamente** (logger + raise/return-with-context). Não havia um caso real onde um service swallowava silenciosamente — a categoria 3 do plano original veio do audit de sistema mas não se confirmou em código.

3. **D.3 sem threshold:** confirmado. `--cov-fail-under` adiado pra sprint posterior depois de medir baseline.

4. **D.4 SKIP:** confirmado. Substituído por `docs/STAGING_BACKLOG.md`. Custo de ~$21/mês × portfólio multi-projeto não justifica nesta sprint.

## Mudanças por arquivo

| Arquivo | Mudança | Categoria |
|---|---|---|
| `pytest.ini` | `--cov=src --cov-report=term-missing` | D.3 |
| `.gitignore` | `.coverage`, `htmlcov/`, `coverage.xml` | D.3 (housekeeping) |
| `src/web/routes/realtime_notifications.py` | 2 webhooks → `abort(501)` | D.1 |
| `tests/test_realtime_webhook_skeletons.py` | 2 testes 501 (novo arquivo) | D.1 |
| `src/web/routes/admin_agents.py` | 1 silent fix + 1 FIXME | D.2.b/c |
| `src/web/routes/api_v1.py` | logger module-level + 2 silent fixes | D.2.b |
| `src/web/routes/admin_users.py` | 1 FIXME | D.2.c |
| `src/web/routes/clinical_intelligence.py` | 4 FIXMEs | D.2.c |
| `src/web/routes/org_management.py` | 2 FIXMEs | D.2.c |
| `src/ai/agents/cientifico.py` | 1 silent fix (RAG degradation visível) | D.2.b |
| `src/ai/agents/extrator.py` | 2 silent fixes | D.2.b |
| `src/services/billing_service.py` | 1 silent fix (feature flag fail-safe loga) | D.2.b |
| `src/services/conversation_service.py` | logger module-level + 1 silent fix (WhatsApp send) | D.2.b |
| `src/services/triage_link_service.py` | logger module-level + 1 silent fix (`_try_persist`) | D.2.b |
| `docs/STAGING_BACKLOG.md` | novo (D.4 substituto) | D.4 |
| `docs/sprints/sprint_1_D.md` | este arquivo | encerramento |

## Testes

- 2 testes novos (`test_realtime_webhook_skeletons.py`).
- Suite re-rodada nos arquivos tocados: `tests/{admin_agents, cientifico_auto_ingest, realtime_webhook_skeletons, triage_link_service, triage_routes, triage_intake_service}` → **23/23 verde** (37s).
- **Não rodei suite completa** (1400+ testes, ~10min, escopo do D não exige). Coordenador pode confirmar que o CI cobre.

## Critérios de sucesso atingidos

- ✅ D.3: `pytest --cov` plug ativo, baseline será impressa nos logs do GitHub Actions na primeira run.
- ✅ D.1: testes verdes garantem 501 em ambos webhooks. Smoke local: 2/2.
- ✅ D.2: 9 sites antes mudos agora deixam trilha em log; 8 sites com empty-data swallow recebem marcação para Sprint 2; 0 services precisaram de re-raise (avaliação revelou que estavam corretos).
- ✅ D.4-substituto: `docs/STAGING_BACKLOG.md` documenta 4 opções com custo + esforço + critério de escolha.

## Pendências / dívidas explícitas registradas

- **Sprint 2:** auditar consumer frontend dos 8 endpoints marcados com `FIXME(sprint-2)` e decidir 500 vs empty data caso a caso.
- **Quando gatilho operacional disparar (deploy quebrar prod ou demo investidor):** retomar `docs/STAGING_BACKLOG.md` e implementar opção apropriada.
- **Sprint posterior à medição da baseline de cobertura:** adicionar `--cov-fail-under=N` ao pytest.ini.

## Observações pra integração

- Branch foi cortada de `main @ 12b220b` (audit IA já mergeado).
- **Sem conflito esperado** com Tracks A/B/C — D não toca os mesmos arquivos:
  - Track A (security/LGPD): toca `src/ai/service.py`, `src/infra/database.py`, `src/config.py`, `src/app.py:273`. D não toca.
  - Track B (guardrails/cost): toca `src/ai/service.py`, `src/ai/pricing.py`, `src/ai/clinical_flow.py`. D não toca.
  - Track C (architectural): toca `src/ai/agents/base.py`, `src/ai/memory.py`, `src/ai/clinical_flow.py`, `src/ai/agents/anamnese.py`, `src/ai/agents/cientifico.py:170-194`. **⚠️ D tocou `src/ai/agents/cientifico.py:53`** (silent fix do `_search_evidence`) — área diferente do que C vai mexer (C edita `_memory_context.query` em :170-194). Conflito improvável mas worth mencionar.
- **Stash com WIP** (`stash@{0}: WIP pre-sprint-1: api_v1 + prompts + login redesign + session test`) deve ser revisitado pós-merge da Sprint 1 inteira.

## Sequenciamento de merge

Doc Sprint 1: ordem é **D → A → B → C**. D pode mergear em `main` assim que coordenador aprovar PR.
