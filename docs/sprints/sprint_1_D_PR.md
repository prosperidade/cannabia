# PR: Sprint 1 Track D — copy/paste no GitHub

**URL para abrir:** https://github.com/prosperidade/cannabia/pull/new/feat/sprint-1-D-tactical

---

## Título do PR

```
Sprint 1 Track D — Tactical hardening (webhooks 501, logging, --cov, staging backlog)
```

## Base / Compare

- **base:** `main`
- **compare:** `feat/sprint-1-D-tactical`

---

## Body do PR

```markdown
## Sumário

Track D do **Sprint 1 CannabIA** — quick wins de menor esforço e baixo risco, primeiro a mergear no sequenciamento `D → A → B → C`.

5 commits, 4-4.5h de esforço executado, 0 linhas removidas, ~245 linhas adicionadas, 2 testes novos.

## Sub-tarefas

| Sub-tarefa | Commit | Status |
|---|---|---|
| **D.3** — `pytest --cov=src --cov-report=term-missing` em `pytest.ini` (sem threshold inicial — baseline) | `1b166e9` | ok |
| **D.1** — Webhooks `/webhook/twilio` e `/webhook/zapi` retornam `abort(501)` em vez de `200 OK` aceitando payload arbitrário + 2 testes novos | `b983db0` | ok |
| **D.2.b** — 9 silent excepts ganham `logger.warning`/`logger.debug` contextual (mantém comportamento de retorno) | `0e77ea1` | ok |
| **D.2.c** — 8 rotas que já logam recebem `# FIXME(sprint-2)` para auditoria de contrato com frontend | `cbf5edf` | ok |
| **D.4-substituto** — `docs/STAGING_BACKLOG.md` + `docs/sprints/sprint_1_D.md` (D.4 original adiado, vira dívida explícita) | `5b5da69` | ok |

## Decisões de Phase 0 confirmadas pelo coordenador

1. **D.1** webhooks → 501 zero-risco (skeleton zumbi sem integração ativa).
2. **D.2** critério híbrido: 9 silent fixes mantêm comportamento, 8 rotas com empty-data viram FIXME(sprint-2). **0 services precisaram re-raise** — auditoria revelou que todos tratavam corretamente (logger + raise/contextualizado). Categoria 3 do plano original não se confirmou em código.
3. **D.3** sem `--cov-fail-under` — baseline primeiro, threshold em sprint posterior.
4. **D.4** SKIP — substituído por `docs/STAGING_BACKLOG.md` documentando 4 opções (Render persistent ~$21/mês, Preview Environments variável, R610 staging container free, status quo) + critério de escolha por cenário.

## Mudanças por arquivo

| Arquivo | Mudança | Categoria |
|---|---|---|
| `pytest.ini` | flags `--cov` | D.3 |
| `.gitignore` | artefatos pytest-cov | D.3 |
| `src/web/routes/realtime_notifications.py` | 2 webhooks → `abort(501)` | D.1 |
| `tests/test_realtime_webhook_skeletons.py` | 2 testes 501 (novo) | D.1 |
| `src/web/routes/admin_agents.py` | 1 silent fix + 1 FIXME | D.2 |
| `src/web/routes/api_v1.py` | logger module-level + 2 silent fixes | D.2 |
| `src/web/routes/admin_users.py` | 1 FIXME | D.2 |
| `src/web/routes/clinical_intelligence.py` | 4 FIXMEs | D.2 |
| `src/web/routes/org_management.py` | 2 FIXMEs | D.2 |
| `src/ai/agents/cientifico.py` | 1 silent fix (RAG degradation visível) | D.2 |
| `src/ai/agents/extrator.py` | 2 silent fixes | D.2 |
| `src/services/billing_service.py` | 1 silent fix (feature flag fail-safe loga) | D.2 |
| `src/services/conversation_service.py` | logger module-level + 1 silent fix | D.2 |
| `src/services/triage_link_service.py` | logger module-level + 1 silent fix | D.2 |
| `docs/STAGING_BACKLOG.md` | novo (D.4 substituto) | D.4 |
| `docs/sprints/sprint_1_D.md` | fechamento Track D | encerramento |

## Test plan

- [x] `pytest tests/test_realtime_webhook_skeletons.py` — **2/2 verde** (29s).
- [x] `pytest tests/{admin_agents, cientifico_auto_ingest, realtime_webhook_skeletons, triage_link_service, triage_routes, triage_intake_service}` — **23/23 verde** (37s).
- [x] Sanity import nos 11 arquivos editados — todos OK.
- [ ] CI run completa em PR — aguardando GitHub Actions.
- [ ] Smoke `/api/v1/health` pós-merge em main.

## Pendências / dívidas explícitas registradas

- **Sprint 2:** auditar consumer frontend dos 8 endpoints com `FIXME(sprint-2)` e decidir 500 vs empty data caso a caso.
- **Quando gatilho operacional disparar** (deploy quebrar prod ou demo investidor): retomar `docs/STAGING_BACKLOG.md`.
- **Sprint posterior à medição da baseline de cobertura:** adicionar `--cov-fail-under=N` ao pytest.ini.

## Sequenciamento

Próximos tracks (em chats separados, branches isoladas):
- **Track A** (security/LGPD): `feat/sprint-1-A-security-lgpd`
- **Track B** (guardrails/cost): `feat/sprint-1-B-guardrails-cost`
- **Track C** (architectural surgery): `feat/sprint-1-C-arch-surgery`

Sem conflito esperado entre D e os outros 3 (verificado em `docs/sprints/sprint_1_D.md` § "Observações pra integração").

Generated with [Claude Code](https://claude.com/claude-code)
```
