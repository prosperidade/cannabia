# Sprint 2 CannabIA — Consolidado (Production Readiness + Compliance + Plumbing)

**Encerrada:** 2026-05-11. **Branch base inicial:** `main @ 01bfa87` (Sprint 1 consolidado). **Branch final:** `main @ 2a08ec1` (PR #33 mergeado).
**Modelo de execução:** multi-track paralelo (6 tracks coordenados em um único chat, com sub-agentes em worktrees isolados — corrigindo a fricção da Sprint 1 de "1 chat por track"). Coordenador: André + Claude.
**Esforço executado:** ~24h código distribuído entre 6 sub-agentes paralelos + ~3h coordenação + rebases + Phase 0 cruzada.

## TL;DR

6 tracks, 6 PRs (#28-#33), todas as 6 dívidas alvo da Sprint 1 resolvidas. **Pipeline clínico agora coleta peso/altura/uso prévio** corretamente (bug de propagação corrigido). **Observabilidade entrou em produção** com defesa rigorosa contra vazamento PII. **Paginação envelope** em endpoints críticos. **Empty-data swallow → 5xx explícito** em 11 sites. **Purge LGPD + retention automatizada** com kill switch operacional. **prompt_registry finalmente ativo** (estava no código mas em fallback eterno por schema drift).

| Track | Sub-tarefas | PR | Status |
|---|---|---|---|
| **AI** — AnamnesisInput extension | AI.1-AI.8 | #28 | ✅ |
| **Obs** — Sentry com PII sanitization | Obs.1-Obs.7 | #29 | ✅ |
| **Page** — Paginação envelope Tier-1 | Page.1-Page.5 | #30 | ✅ |
| **LGPD** — Purge + retention + kill switch | LGPD.1-LGPD.9 + commit follow-up | #31 | ✅ |
| **Audit** — Empty-data → 5xx em 11 sites | Audit.0-Audit.6 | #32 | ✅ |
| **Reg** — prompt_registry schema fix + plug | Reg.0-Reg.8 + rename 044→046 | #33 | ✅ |

## Sub-tarefas mergeadas (cronológico de merge em main)

| # | Track | Sub-tarefa | Commit | PR |
|---|---|---|---|---|
| 1 | AI | Estende AnamnesisInput + corrige bug propagação triage_intake_service | `1f6b0fe` | #28 |
| 2 | Obs | Plug Sentry com sanitization PII LGPD-safe | `51e412a` | #29 |
| 3 | Page | Paginação envelope nos Tier-1 endpoints + helper compartilhado | `be539c1` | #30 |
| 4 | LGPD | Purge retroativo + retention policy ai_audit_logs | `9bee33c` | #31 |
| 5 | LGPD (follow-up) | Kill switch `LGPD_PURGE_ENABLED` no cron de retention | `42dd58c` | #31 |
| 6 | Audit | Empty-data swallow → 500/503 em 11 endpoints | `6a3f495` (rebased de `cea0ed6`) | #32 |
| 7 | Reg | Plug prompt_registry + backfill prompt_version REAL | `58ba5f4` (rebased de `68417ae`) | #33 |
| 8 | Reg (follow-up) | Renumera migration 044 → 046 (conflito com LGPD) | `b7e55d3` | #33 |

## Decisões arquiteturais que entraram em produto

### Track AI (AnamnesisInput extension)

- **Surpresa do Phase 0:** wizard de triagem (`step-dados-fisicos.tsx` + `types-triagem.ts`) JÁ COLETAVA peso/altura/uso prévio. Bug estava em [src/services/triage_intake_service.py:190-198](../../src/services/triage_intake_service.py#L190-L198) que **dropava os 3 campos** ao construir `AnamnesisInput`. Não era gap de UI — era bug de propagação puro.
- **Q-AI-3 (a) — Optional + manter defaults como fallback:** novos campos em [AnamnesisInput](../../src/ai/schemas.py) são `Optional[float]`/`Optional[bool]`. [clinical_flow.py:87-92](../../src/ai/clinical_flow.py#L87-L92) mantém defaults conservadores (`DOSAGE_DEFAULT_WEIGHT_KG=70.0`, `DOSAGE_DEFAULT_PRIOR_USE=False`) como fallback de back-compat — WhatsApp ainda não coleta e isso é OK.
- **Q-AI-4 (b) — Badge condicional preservado:** `PrescriptionResultBlock` em [atendimentos/[id]/page.tsx:97-104](../../frontend/app/atendimentos/[id]/page.tsx#L97-L104) ainda mostra "Dosagem com defaults conservadores" quando aplicável, mas tooltip atualizado (sem mais "Sprint 2 estende a anamnese").
- **Q-AI-5 (a) — Migração de pacientes legados:** relatórios pré-Sprint-2 mantêm `dosage_defaults_used=True` (snapshot persistido). Sem backfill — auditoria forense preservada.

### Track Obs (Sentry observability)

- **Q-Obs-1 (soft) — DSN ausente em prod NÃO raise** ([config.py:43-65](../../src/config.py#L43-L65)). App sobe sem Sentry vs quebrar deploy. Sprint 3 endurece pra raise.
- **Q-Obs-2 (defesa em camadas):** [_sentry_before_send](../../src/infra/observability.py) combina denylist nativa (`send_default_pii=False`) + `sanitize_clinical_payload` (A.3) walk em `request.data`, `extra`, `breadcrumbs`, `frames[].vars`.
- **Q-Obs-3 — Traces OFF na Sprint 2:** `traces_sample_rate=0.0`. Performance traces caros, valor baixo até ter SLO definido.
- **Q-Obs-4 — `include_local_variables=False`:** PII em traceback locals = LGPD breach. Mais seguro perder algum contexto debug. (Nome migrou de `with_locals` em SDK 2.x — adapt natural.)
- **Q-Obs-5 — LoggingIntegration granular:** ERROR/CRITICAL viram event Sentry; WARNING vira breadcrumb. Evita spam.
- **Fail-safe rigoroso:** se `sanitize_clinical_payload` raise no before_send, evento é **DROPADO** (return None). Perder telemetria > vazar PII.

### Track Page (Pagination envelope)

- **Q-Page-1 (híbrido):** offset-based pra admin tables; cursor pra feeds temporais (`list_messages` já existia com `before_id`). Sprint 2 só implementa offset.
- **Q-Page-2 — Envelope no body:** `{items, total, limit, offset, has_more}`. NÃO X-Total-Count header (CORS expose pain).
- **Q-Page-3 — `?legacy=1` escape hatch:** default=50 sempre; flag `?legacy=1` retorna bare array por 1 sprint. Sprint 3 deprecation.
- **Q-Page-5 (silent clamp) — limit > 200:** logger.warning + clamp pra `max_limit`. Sprint 2 silencia; Sprint 3 vira HTTP 400.
- **Q-Page-6 — COUNT opt-in:** `?include_total=1` ativo retorna `total: int`; padrão `total: null` + `has_more` calculado via LIMIT+1 trick. Tabelas grandes (`ai_audit_logs`) salvam latência.
- **Q-Page-4 escopo reduzido:** Tier-1 (4 endpoints) entregue. Tier-2 (4 endpoints) + frontend consumers → Sprint 3.

### Track LGPD (Purge + retention)

- **Q-LGPD-1 — Cutoff fixo:** `2026-05-10T17:00:00+00:00` (1h margin pós-merge A.3 às ~13:05 BRT).
- **Q-LGPD-3 — Archive antes de delete:** rows aposentados copiados pra `ai_audit_logs_archive` antes de DELETE. Forensics preservada por 5y (default `LGPD_AUDIT_ARCHIVE_RETENTION_DAYS=1825`).
- **Q-LGPD-4 — Render Cron Job:** pg_cron NÃO disponível em Render basic-256mb. Cron service `cannabia-audit-retention` (`0 4 * * *`) com `python -m scripts.retention_audit_logs`.
- **Q-LGPD-5 — Purge manual 1x idempotente:** script com `--dry-run`/`--commit` + tabela `ai_audit_purge_processed_ids` pra resume. Snapshot table `ai_audit_logs_pre_redact_backup_*` TTL 30d.
- **Kill switch operacional (decisão coordenador pós-merge):** `LGPD_PURGE_ENABLED=false` default. Cron continua agendado (valida agendamento + DATABASE_URL) mas roda como no-op até OK jurídico → flip pra `true` no Render dashboard.
- **Q-LGPD-2 — Prazos defensáveis MAS production run aguarda OK jurídico:** 90d detail / 365d critical (`security_blocked`+`error`) / 5y archive.
- **Q-LGPD-6 — Dívida 4 LGPD (PII em medical_record/anamnesis_reports) explicitamente OUT-OF-SCOPE Sprint 2:** essas tabelas têm justificativa clínica (prontuário oficial, não log operacional). Decisão arquitetural pendente (encrypt at-rest vs auditar acesso via audit_trail). → Sprint 4.

### Track Audit (Empty-data → 5xx)

- **Q-Audit-3 (granularidade simples):** `OperationalError → 503 "database_unavailable"`; `Exception → 500 "internal_error"`. Sem 4xx específico exceto onde semanticamente faz sentido (lab_analysis 404).
- **Q-Audit-6 — Expandir escopo de 7 → 11 sites:** os 4 análogos em `org_management.py` (`/doctors`, `/stock`, `/billing`, `/financial`) tinham o mesmo pattern de swallow sem FIXME marcado. Coerência arquitetural > conservadorismo de escopo.
- **Q-Audit-7 — Site #6 (`clinical_intelligence.py:183`) ganhou 404 explícito:** quando `patient_id` é passado mas `cursor.fetchone()` retorna None, **NÃO** é erro técnico — é "not found". Separação semântica antes do except.
- **Q-Audit-5 — Ordem de merge:** Audit DEPENDE de Obs deployado em produção primeiro (senão 5xx novos ficam invisíveis até próximo deploy do Sentry). Coordenador validou Sentry capturando antes do merge Audit.
- **ApiError infrastructure reusada:** frontend [api.ts:49-82](../../frontend/lib/api.ts#L49-L82) já lançava `ApiError` em `!response.ok`. Zero refactor frontend — só adaptar callers conforme necessário.

### Track Reg (prompt_registry alignment + plug)

- **CRITICAL SURPRISE do Phase 0:** [src/ai/prompt_registry.py](../../src/ai/prompt_registry.py) (317 linhas) **JÁ ESTAVA 100% IMPLEMENTADO**, mas com schema drift sutil: código usava `prompt_key`/`is_active`, DB (migration 001) tinha `name`/`active`. Resultado: `load_from_db()` falhava silenciosamente, fallback hardcoded eterno. **DB-first NUNCA ATIVAVA.** Ninguém percebeu porque log do erro era DEBUG.
- **Q-Reg-1 — ALTER TABLE aliasing:** migration 046 adiciona `prompt_key VARCHAR(50)` + `is_active BOOLEAN GENERATED ALWAYS AS (active) STORED` + metadata extra. Backfill `prompt_key = name`. Compat 100% (active continua existindo).
- **Q-Reg-2 — TTL cache 60s (era 300):** mais responsivo em piloto. Override via `PROMPT_CACHE_TTL` env var.
- **Q-Reg-3 — prompts.py CONTINUA source-of-truth:** seed snapshot + hardcoded fallback. DB é override versionado opcional. Não invertemos a hierarquia.
- **Q-Reg-5 — `activate_prompt_version` atrás de feature flag:** `FF_PROMPT_REGISTRY_ADMIN` default OFF. Sprint 3 enable + UI admin.
- **Q-Reg-6 — Pre-flow paths gravam `"n/a"`:** billing_blocked/security_blocked/validation_error/error em [service.py](../../src/ai/service.py) gravam `prompt_version="n/a"`+`prompt_hash="n/a"` honestamente (em vez de mentir com snapshot fake).
- **Q-Reg-7 — Simplificação no clinical_flow (não invadir agentes):** [clinical_flow.py:167-171](../../src/ai/clinical_flow.py#L167-L171) chama `get_prompt()` direto pra obter os 4 metas (anamnesis/treatment_plan/prescriber_system/scientific_report+rag). NÃO propaga via `AgentResult.prompt_meta` — Sprint 3 endurece se necessário.
- **PRESCRIBER_*_PROMPT adicionados ao registry:** Sprint 1 C.1 entregou prescritor sem versionamento. Reg corrige.
- **Migration 044 → 046:** LGPD reservou 044/045 primeiro; Reg renumerou no rebase pós-merge sequencial.
- **Pós-merge crítico:** `python -m scripts.seed_prompts --commit` (executado pelo coordenador no Render). Sem isso, DB continua vazio → fallback eterno → bug se reintroduz.

## Mudanças estruturais que sobreviveram em main

| Categoria | Arquivo | Origem |
|---|---|---|
| **Schema** | `src/ai/schemas.py` (AnamnesisInput +3 Optional Fields) | AI |
| **Schema** | `migrations/044_audit_purge_events.sql` + `045_audit_archive_retention.sql` + `046_prompt_registry_alignment.sql` (UP + DOWN) | LGPD + Reg |
| **AI Pipeline** | `src/services/triage_intake_service.py` (bug fix propagação) | AI |
| **AI Pipeline** | `src/services/anamnesis_flow.py` (WhatsApp passa None explícito) | AI |
| **AI Pipeline** | `src/ai/clinical_flow.py` (prompts_used snapshot via get_prompt) | Reg |
| **AI Pipeline** | `src/ai/service.py` (`_aggregate_prompt_version`/`_aggregate_prompt_hash` helpers + pre-flow "n/a") | Reg |
| **AI Pipeline** | `src/ai/prompt_registry.py` (TTL 60s + prescriber_system/_user adicionados) | Reg |
| **AI Pipeline** | `src/ai/chains.py` + `src/ai/prescriber.py` (chamadas `get_prompt().text`) | Reg |
| **Observability** | `src/infra/observability.py` (novo — `init_sentry` + `_sentry_before_send` + `tag_request`) | Obs |
| **Observability** | `src/config.py` (`_get_sentry_config` soft pattern) | Obs |
| **Observability** | `src/app.py` (init + before_request tag) | Obs |
| **Web/API** | `src/web/pagination.py` (novo — parse + envelope + LIMIT+1 trick) | Page |
| **Web/API** | `src/repositories/{appointment,anamnesis,conversation,ai_audit}_repository.py` (kwargs `limit`/`offset`/`include_total`/`paginated`) | Page |
| **Web/API** | `src/web/routes/{admin_users,clinical_intelligence,org_management}.py` (try/except → OperationalError 503 / Exception 500) | Audit |
| **LGPD/Ops** | `scripts/purge_audit_pii_pre_a3.py` + `scripts/retention_audit_logs.py` + `scripts/seed_prompts.py` | LGPD + Reg |
| **LGPD/Ops** | `render.yaml` (service cron `cannabia-audit-retention` + `SENTRY_DSN` env + `LGPD_PURGE_ENABLED=false` kill switch) | LGPD + Obs |
| **Frontend** | `frontend/lib/types.ts` (`ApiListMeta`, `PaginatedResult<T>`, `AttendanceListItem`) | Page |
| **Frontend** | `frontend/app/atendimentos/[id]/page.tsx` (tooltip do badge defaults atualizado) | AI |
| **Docs** | `docs/LGPD_OPERATIONS.md` (runbook), `docs/api/pagination.md` (contrato), `docs/sprints/sprint_2_Obs.md` (Sentry runbook) | LGPD + Page + Obs |

## Cobertura de testes — adições da sprint

| Suite | Quantidade | Origem |
|---|---|---|
| `tests/test_clinical_flow.py` (test_dosage_defaults_used_false_when_anamnesis_complete + regressions) | +3 | AI |
| `tests/test_triage_intake_service.py` (regression bug propagação) | +1 | AI |
| `tests/test_observability.py` (soft-off, redact PII, fail-drop, tag defensivo) | 4 | Obs |
| `tests/web/test_pagination.py` (defaults/clamp/legacy/envelope/has_more) | 6 | Page |
| `tests/test_audit_redaction.py` (3 testes idempotência adicionais) | +3 | LGPD |
| `tests/test_purge_script.py` (dry-run/commit/idempotência/resume) | 9 | LGPD |
| `tests/test_retention_script.py` (env_int/thresholds/archive/race/e2e cron event) | 8 | LGPD |
| `tests/test_audit_error_handling.py` (OperationalError 503 + Exception 500 + 404 lab) | 11 | Audit |
| `tests/test_prompt_registry_integration.py` (fallback hardcoded/cache/key inexistente/flow/service real) | 7 | Reg |

**Smoke completo pós-merges (2026-05-11):** `1559 passed, 194 skipped, 3 failed + 1 error em 194.80s` (3min14s). As 4 falhas pré-existentes da Sprint 1 dependem de Postgres em `:5434` (Docker não up local) — `test_database_pool` x3 + `test_audit_redaction::test_repository_sanitizes_*`. **Zero regressões; +55 testes vs Sprint 1.**

## Critérios de sucesso atingidos

- ✅ **AI:** `dosage_defaults_used=False` quando wizard alimenta os 3 campos (era True em 100% dos atendimentos).
- ✅ **Obs:** Sentry capturando em prod com PII redacted em request.data, extra, breadcrumbs, frames[].vars. Soft pattern garante deploy não quebra se DSN ausente.
- ✅ **Page:** 4 endpoints Tier-1 servindo envelope `Paginated<T>`. `?legacy=1` mantém compat. Sem N+1 queries.
- ✅ **Audit:** 11 endpoints retornando 5xx explícito em erro técnico (era empty data swallow). FIXMEs removidos.
- ✅ **LGPD:** Purge script idempotente com dry-run/commit + retention cron com kill switch. Production run aguarda OK jurídico.
- ✅ **Reg:** `ai_audit_logs.prompt_version` e `prompt_hash` deixam de ser placeholder `v1.0`/`sha256("v1.0")`. Hash agregado deterministico das 4 stages. Pós-merge `seed_prompts --commit` rodado em prod.

## Pendências operacionais (não-código)

1. ⏳ **Sprint 1 A.1 — Rotação de keys no Render** (carry-over da Sprint 1, ainda pendente).
2. ⏳ **OK jurídico pros prazos de retention LGPD** (90d/365d/5y) antes de virar `LGPD_PURGE_ENABLED=true`.
3. ⏳ **Validar Sentry em prod** capturando erros reais nos próximos dias (Obs deployed mas precisa ver volume real de eventos pra calibrar `sample_rate`).
4. ⏳ **Production run do purge retroativo** após OK jurídico: dry-run → review output → commit → confirma contagem → DROP backup table após 30d (`docs/LGPD_OPERATIONS.md` runbook).

## Dívidas registradas pra Sprints 3-4+

### Sprint 3 (production hardening + ANVISA kickoff — em planejamento)

| Origem | Dívida | Doc/issue |
|---|---|---|
| Sprint 2 Page | Tier-2 backend (4 endpoints faltantes) + migrar frontend consumers pra envelope `Paginated<T>` | Inline em [pagination.md](../api/pagination.md) |
| Sprint 2 Obs | Endurecer Sentry: DSN raise em prod (vs soft warn), `traces_sample_rate=0.05`, `with_locals=True` com processor robusto | [sprint_2_Obs.md](sprint_2_Obs.md) |
| Sprint 2 Reg | UI admin do prompt_registry + habilitar `FF_PROMPT_REGISTRY_ADMIN` | Inline no Track Reg |
| Sprint 1 C.1 Dívida 6 | Cientifico cita evidência baseado em `final_dosage` (não em treatment_plan draft) | [BACKLOG_AGENTE_PRESCRITOR.md](../BACKLOG_AGENTE_PRESCRITOR.md) |
| Sprint 1 B.1 | Pattern 7 `_OUTPUT_DANGER_PATTERNS` captura nome+valor de env vars | `tests/test_output_guardrail.py:105` FIXME |
| Sprint 2 Audit | Deprecar `?legacy=1` flag de paginação | [pagination.md](../api/pagination.md) |
| Sprint 2 Audit | `limit > max` virar HTTP 400 (Sprint 2 silencia + log) | Inline em `src/web/pagination.py` |
| Executive C1+C2 | Popular `data/legislation/` com RDC 327/660 + Lei 11.343 + upload Google Files API | [22_EXECUTIVE_BACKLOG.md Frente C](../22_EXECUTIVE_BACKLOG.md) |
| Executive I1 | Aplicar migrations 022/023 (integrity hardening + TIMESTAMPTZ) — prontas, pendente APPLY | Frente I (SCC kickoff) |

### Sprint 4 (eval harness + clinical expansion + security deep work)

| Origem | Dívida | Doc/issue |
|---|---|---|
| Sprint 1 B.1 | Eval harness com corpus real → calibrar threshold Camada 4 (sanitize → bloqueio em alta confidence) | `sprint_1_B.md` |
| Sprint 1 A.3 Dívida 3 | Rotação SECRET_KEY com re-encryption schema (versioned ENCRYPTION_KEY) | [BACKLOG_LGPD.md Dívida 3](../BACKLOG_LGPD.md) |
| Sprint 1 A.3 Dívida 4 | PII em medical_record_entries + anamnesis_reports — design arquitetural (encrypt at-rest vs auditar acesso) | [BACKLOG_LGPD.md Dívida 4](../BACKLOG_LGPD.md) |
| Sprint 1 C.3 Dívida 1 | Expandir CONDITION_PROTOCOLS (10 novas: glaucoma, Alzheimer, ELA, etc) — exige revisor médico | [BACKLOG_AGENTE_PRESCRITOR.md](../BACKLOG_AGENTE_PRESCRITOR.md) |
| Sprint 1 C.3 Dívida 2 | Expandir CYP450_INTERACTIONS (~25 drugs) — exige revisor farmacológico | idem |
| Sprint 1 C.3 Dívida 3 | Safety clamp granular (Child-Pugh, clearance renal, IMC, sexo, polifarmácia, cardio) | idem |
| Sprint 1 C.1 Dívida 5 | `safety_clamp_applied` comparação raw-vs-clamped exata (refactor de `run_prescriber`) | idem |

### Sprint 5+ (SCC ANVISA — multi-sprint épico)

Frente I do Executive (I2-I12): Governance Hub, Seed-to-Patient Traceability, Member Registry, Pharmacovigilance estruturado, Regulatory Reporting, Blockchain anchoring, Templates regulatórios, Piloto associação parceira. Ver [22_EXECUTIVE_BACKLOG.md](../22_EXECUTIVE_BACKLOG.md).

### Sem prazo (gatilho operacional)

- C7 (extração de conhecimento agregado) — sprint dedicada per Executive.
- Staging environment quando deploy quebrar prod ou demo investidor.
- `--cov-fail-under=N` quando baseline medida.
- Migração `gemini-1.5-flash` → `gemini-2.5-flash` antes de jun/2026.

## Lições aprendidas

1. **Memory cache mente — sempre verifique o código real.** Os hooks injetaram observações dizendo que `service.py` já estava wired pra `prescription_result` (Sprint 1 C.1) e que `prompt_registry.py` precisava ser criado from scratch (Sprint 2 Reg) — **ambas falsas**. Verificar `git log` + `Read` antes de aceitar contexto persistido.
2. **Schema drift silencioso é o pior tipo.** `prompt_registry` ficou em fallback eterno por meses sem ninguém notar porque o log do erro era DEBUG. Sprint 3 lesson: sempre logar fallbacks como WARNING.
3. **Bug de propagação > gap de UI.** Track AI ia ser ~12h pra criar widget novo; virou ~3.75h ao descobrir que UI já existia e bug era 3 linhas em service. **Phase 0 com cruzamento de docs+código economiza dias.**
4. **Sub-agentes em worktrees isolados funcionam.** Sprint 1 = 1 chat por track (fricção). Sprint 2 = 1 chat coordenador + N worktrees paralelos. Conflito de merge resolvido manualmente em rebase (migrations 044) — risco controlado.
5. **Defaults conservadores como fallback > requireds quebrando back-compat.** AnamnesisInput tornou os 3 campos Optional. WhatsApp ainda não coleta → continua funcionando com defaults. Migração gradual.
6. **Kill switch >>>>>> "espera o juridico".** Render Cron continua agendado validando agendamento + DATABASE_URL, mas roda como no-op até flag virar. Primeiro tick pós-OK é < 24h sem precisar re-deploy.
7. **Numeração de migrations conflita quando paralelo.** 044 conflitou entre Reg e LGPD. Resolvido via rebase + rename. Sprint 3: considerar reservar números antes de Phase 0 finalizar (ex: "Track X usa 044, Track Y usa 045").
8. **Track B (Sprint 1) plantou semente que C.1 e Reg colheram.** `tokens_per_stage` extensível permitiu adicionar entry "prescription" (C.1) e depois `prompt_meta` (Reg) sem refactor em service.py. Estruturas extensíveis pagam dividendo.

## Próximo passo: Sprint 3

**Tema:** Production Hardening + ANVISA Kickoff. **Em planejamento** — 5 tracks recomendados após cruzamento docs×código:

1. **SCC-I1** — Aplicar migrations 022/023 (prontas, pendente APPLY). Pré-requisito da Frente I (Sandbox Compliance Core ANVISA).
2. **Legislação-Real** — Popular `data/legislation/` com RDC 327/660 + Lei 11.343, upload Google Files API.
3. **Cientifico-Final-Dosagem** — Dívida 6 do Prescritor.
4. **Obs-Harden** — DSN raise em prod, `traces_sample_rate=0.05`, processor robusto.
5. **Page-Migration** — Frontend consumers + Tier-2 backend.

Detalhes em discussão. Itens explicitamente OUT-OF-SCOPE Sprint 3: expansão clínica (Sprint 4 com revisor), SECRET_KEY rotation (Sprint 4 — complexo), C7 (sprint dedicada), SCC I2-I12 (multi-sprint).

## Encerramento

**Sprint 2 fechada — 6 tracks, 8 commits (6 PRs principais + 2 follow-ups), 6 dívidas Sprint 1 resolvidas.**

- **Track AI:** AnamnesisInput estendido + bug propagação corrigido.
- **Track Obs:** Sentry com defesa rigorosa contra vazamento PII em produção.
- **Track Page:** Paginação envelope nos endpoints Tier-1 críticos.
- **Track LGPD:** Purge retroativo + retention automatizada com kill switch.
- **Track Audit:** Empty-data swallow → 5xx em 11 endpoints (D.2.c resolvido).
- **Track Reg:** prompt_registry finalmente ativo (schema drift sutil corrigido).

**Próximo:** Sprint 3 em planejamento — production hardening + ANVISA Sandbox Compliance Core kickoff.
