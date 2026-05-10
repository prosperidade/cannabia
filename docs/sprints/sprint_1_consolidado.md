# Sprint 1 CannabIA — Consolidado (Foundation: Security + LGPD + Guardrails + Architectural Surgery)

**Encerrada:** 2026-05-10. **Branch base inicial:** `main @ 12b220b` (auditoria de agentes IA). **Branch final:** `main @ f6d7514` (PR #27 mergeado).
**Modelo de execução:** multi-track paralelo (A/B/C/D em chats dedicados). Coordenador: André + Claude na conversa principal.
**Esforço executado:** ~17h código + ~3h docs + Phase 0 reviews. Original estimado: 17–21h.

## TL;DR

4 tracks, 9 PRs, 11 sub-tarefas mergeadas (1 operacional pendente). **Pipeline clínico cresceu de 3 stages pra 4** com Prescritor entrando entre Tratamento e Cientifico. **Audit logs LGPD-compliant forward** via redaction estrutural. **Camada 4 de guardrails saiu de dead code pra produção**. **Cost honesto por stage** com Gemini pricing correto. **MemPalace 100% extirpado**.

| Track | Sub-tarefas | PRs | Status |
|---|---|---|---|
| **D** — Tactical hardening | D.1, D.2.b, D.2.c, D.3, D.4-substituto | #19 | ✅ |
| **B** — Guardrails + Cost honesto | B.1, B.2, B.3 | #20, #21, #22 | ✅ |
| **A** — Security + LGPD critical | A.2, A.3, A.4 | #23, #24, #25 | ✅ code-side |
| **A.1** — rotação keys (Render) | — | — | ⏳ pendente do user, operacional |
| **C** — Architectural surgery | C.1, C.2, C.3 | #26, #27 | ✅ |

## Sub-tarefas mergeadas (cronológico)

| # | Track | Sub-tarefa | Commit | PR |
|---|---|---|---|---|
| 1 | D.3 | `pytest --cov=src` em pytest.ini | `1b166e9` | #19 |
| 2 | D.1 | Webhooks Twilio + Z-API → 501 | `b983db0` | #19 |
| 3 | D.2.b | logger.warning/debug em 9 silent excepts | `0e77ea1` | #19 |
| 4 | D.2.c | FIXME(sprint-2) em 8 rotas com empty-data swallow | `cbf5edf` | #19 |
| 5 | D.4-sub | `docs/STAGING_BACKLOG.md` (substitui staging env) | `5b5da69` | #19 |
| 6 | B.3 | `timings_ms` populado por stage via `time.perf_counter()` | `7b2059e` | #20 |
| 7 | B.2 | Cost honesto por stage + Gemini pricing | `e24162c` | #21 |
| 8 | B.1 | Camada 4 output guardrail plugada em service.py | `db42388` | #22 |
| 9 | A.2 | `SimpleConnectionPool` → `ThreadedConnectionPool` | `5d4c054` | #23 |
| 10 | A.4 | SECRET_KEY hardening 3 pontos + ENCRYPTION_KEY check + next_url | `3b4cd8e` | #24 |
| 11 | A.3 | PII redaction estrutural em `ai_audit_logs` | `aae1237` | #25 |
| 12 | C.2 | Extirpa MemPalace path completamente | `dd01d44` | #26 |
| 13 | C.1+C.3 | Prescritor no clinical_flow + telemetria + UI + backlog dívidas | `779cf11` | #27 |

## Decisões arquiteturais que entraram em produto

### Track A (Security + LGPD)

- **Q-A1 (c) híbrido — PII redaction estrutural:** `sanitize_clinical_payload` em [src/ai/audit_redaction.py](../../src/ai/audit_redaction.py) faz walk recursivo. Keys que matcham `SENSITIVE_KEYS` (40+ keys pt/en) → value-redacted integral. String-leaves passam por 14 regex (CPF, email, phone, RG, CRM, address, CEP, SUS-com-contexto, patient name).
- **R1 — Single point of intervention:** sanitização aplicada em [src/repositories/ai_audit_repository.py:67-68](../../src/repositories/ai_audit_repository.py#L67-L68), NÃO nos 6+ call sites de `save_ai_audit_log`. Confirmado em produção: C.1 plugou `prescription_result` sem 1 linha de sanitization extra.
- **Q-A2 — SUS regex contexto-explícito:** `\b\d{15}\b` solto dava falso positivo (códigos de exame). Regex agora exige `SUS`/`CNS`/`cartão saúde` antes do número.
- **Q-A3 (c) híbrido FLASK_ENV — SECRET_KEY:** `_get_secret_key_or_fail()` em [src/config.py](../../src/config.py) raise em prod, random in-memory + warning em dev. Aplicado nos 3 pontos simultaneamente (`config.py`, `app.py:104`, `crypto.py:30`).
- **Q-A5 — ENCRYPTION_KEY check defense-in-depth:** `_check_encryption_key_or_fail()` raise em prod sem `ENCRYPTION_KEY` (Render dashboard já gera via `generateValue: true`).
- **Sanitizer fail-safe obrigatório:** NUNCA raise; em erro interno devolve `{"_redaction_failed": True, "_payload_keys": [...], "_error": ...}`. Audit log nunca desaparece por causa de erro de redaction.
- **next_url validation** em [src/app.py](../../src/app.py): `_validate_next_url` (module-level, testável isolado) — must start with `/` E não conter `://` E não conter `\\`. Caso contrário, redirect pra `/`.

### Track B (Guardrails + Cost honesto)

- **B.3 solução (a):** `time.perf_counter()` manual em volta de cada `with measure(...)` — 6 linhas, isolado, não toca `src/infra/metrics.py`.
- **B.2 escopo expandido — cost subnotificado descoberto durante Phase 0:** `service.py:155` calculava custo agregado com modelo único `"gpt-4o-mini"` para soma dos 3 stages. Quando RAG ativo (caminho normal), tokens do Gemini eram contados como OpenAI — cost subnotificado. B.2 retorna `tokens_per_stage` extensível e soma `calculate_cost` por stage com modelo correto. **Estrutura usada por C.1** sem refactor adicional.
- **B.2 estrutura extensível:** `tokens_per_stage = {stage_name: {"model": str, "tokens": {"input": int, "output": int}}}`. C.1 adicionou entry `"prescription"` zero-código em service.py.
- **B.1 helper recursivo nos string-leaves:** ao invés de `json.dumps + regex.sub + parse` (corrompe estrutura JSON), `apply_to_output_dict` aplica `sanitize_output` em cada string-leaf preservando tipos.
- **B.1 calibração progressiva:** Camada 4 **NÃO bloqueia** — sanitiza + sinaliza via `_guardrail_output.requires_review=True`. Sprint 4 (eval harness) endurece com base em corpus real.
- **Pricing Gemini com comentário legacy:** valores `$0.075/1M` input + `$0.30/1M` output usados; registrada dívida de migração pra `gemini-2.5-flash` antes de jun/2026 em [docs/BACKLOG_AI_MIGRATION.md](../BACKLOG_AI_MIGRATION.md).

### Track C (Architectural Surgery)

- **C.2 — MemPalace extirpado:** classificado como fraude em 2026-04-24. 191 linhas de `src/ai/memory.py` deletadas; `Orchestrator` deletado; `BaseAgent` perdeu `palace_room`/`recall_memory`/`remember`/`remember_fact`/`get_diary`; 8 agentes limpos; 6 call sites de `self.remember()` removidos; `mempalace>=3.0.0` removido do requirements.txt + desinstalado do venv.
- **Q-C1 (a) — Pipeline 4-stage:** Prescritor entra **APÓS** Tratamento e **ANTES** de Cientifico (Anamnese → Tratamento → **Prescritor** → Cientifico).
- **Cientifico INALTERADO** (decisão coordenador C.1): continua consumindo `treatment_plan` (TreatmentPlan shape). Forçar refactor pra consumir `DosageRecommendation` multiplicava risco. Flow retorna AMBOS `treatment_plan` E `prescription_result` paralelos. Documentado como **Dívida 6** pra Sprint 2/3 unificar.
- **`safety_clamp_applied` heurística honesta:** `bool(cyp450 or contraindications)` derivado dos sinais do Rules Engine. Não comparei "LLM raw vs clamped" porque `run_prescriber()` não expõe a recomendação pré-clamp — refactor opcional documentado como **Dívida 5** (Sprint 4 ou skip).
- **Defaults conservadores `weight_kg=70.0` + `prior_cannabis_use=False`:** `AnamnesisInput` não coleta esses campos hoje; flag `dosage_defaults_used=True` ativa em 100% dos atendimentos atualmente. Badge "ⓘ Dosagem com defaults conservadores" no frontend sinaliza ao médico que ele deve ajustar manualmente. **Dívida 4** (alta prioridade Sprint 2: estender AnamnesisInput + widget de triagem).
- **`risk_level` normalizado proativamente em clinical_flow:** Anamnese às vezes retorna `"medio"` ou outros valores não aceitos pelo `DosageInput.validate_risk` (só aceita baixo/moderado/alto). Fallback `moderado` evita ValidationError em produção.
- **Migration 043 (não 125):** anchor file estava errado — última real era 042. Renumerada na Phase 0.
- **Frontend display em `/atendimentos/[id]` standalone:** decisão UX coordenador C.1.4. NÃO toca `/med/prescricao/*` nem `prescription_contract` (sistema separado de emissão formal). Componente inline `PrescriptionResultBlock` com badges + tooltips + lista CYP450 + timeline de titulação.

### Track D (Tactical hardening)

- **D.1 webhooks → 501** ao invés de 200/silent. Twilio + Z-API são skeletons sem integração ativa hoje. 501 é semanticamente correto e zero-risco-de-regressão.
- **D.2 critério híbrido — separação por intent:** 9 silent fixes ganham `logger.warning`/`logger.debug` mantendo comportamento (fail-safe ou empty fallback intencional); 8 routes com empty-data swallow ganham `# FIXME(sprint-2)` pra auditar contrato com frontend; 0 services precisaram de re-raise (audit revelou que estavam corretos).
- **D.3 `--cov=src` sem threshold:** `--cov-fail-under` adiado pra sprint posterior (mede baseline primeiro).
- **D.4 staging SKIP → backlog:** custo de ~$21/mês × portfólio multi-projeto não justifica. Substituído por [docs/STAGING_BACKLOG.md](../STAGING_BACKLOG.md) com 4 opções.

## Mudanças estruturais que sobreviveram em main

| Categoria | Arquivo | Origem |
|---|---|---|
| **PII / Audit** | `src/ai/audit_redaction.py` (novo) | A.3 |
| **PII / Audit** | `src/repositories/ai_audit_repository.py` (sanitize + 3 colunas Prescritor) | A.3 + C.1 |
| **Security** | `src/config.py` (`_get_secret_key_or_fail` + `_check_encryption_key_or_fail`) | A.4 |
| **Security** | `src/app.py` (`_validate_next_url`) | A.4 |
| **Security** | `src/infra/crypto.py` (importa SECRET_KEY validada) | A.4 |
| **Infra** | `src/infra/database.py` (`ThreadedConnectionPool`) | A.2 |
| **AI Pipeline** | `src/ai/clinical_flow.py` (4 stages, defaults, normalização risk_level) | B.3 + B.2 + C.1 |
| **AI Pipeline** | `src/ai/agents/prescritor.py` (`execute()` constrói `prescription_result`) | C.1 |
| **AI Pipeline** | `src/ai/schemas.py` (`PrescriptionResult` Pydantic) | C.1 |
| **AI Pipeline** | `src/ai/service.py` (Camada 4 + cost por stage + telemetria Prescritor) | B.1 + B.2 + C.1 |
| **AI Pipeline** | `src/ai/guardrails.py` (`_sanitize_string_leaves` + `apply_to_output_dict`) | B.1 |
| **AI Pipeline** | `src/ai/pricing.py` (`gemini-1.5-flash` entry) | B.2 |
| **AI Pipeline** | `src/ai/agents/base.py` (sem `palace_room`/recall/remember) | C.2 |
| **DB schema** | `migrations/043_prescritor_telemetry.sql` (UP + DOWN) | C.1 |
| **Routes** | `src/web/routes/realtime_notifications.py` (501 webhooks) | D.1 |
| **Routes** | logger.warning em 9 sites (admin_agents, api_v1, cientifico, extrator, billing_service, conversation_service, triage_link_service) | D.2.b |
| **Frontend** | `frontend/lib/types.ts` (+`prescription_result?`) | C.1 |
| **Frontend** | `frontend/app/atendimentos/[id]/page.tsx` (`PrescriptionResultBlock`) | C.1 |

## Cobertura de testes — adições da sprint

| Suite | Quantidade | Origem |
|---|---|---|
| `tests/test_database_pool.py` (3 testes) | 3 | A.2 |
| `tests/test_hardening.py` (9 testes / 21 cases) | 9 | A.4 |
| `tests/test_audit_redaction.py` (6 testes — 4 unit + 1 fail-safe + 1 DB roundtrip) | 6 | A.3 |
| `tests/test_pricing.py` | 8 | B.2 |
| `tests/test_output_guardrail.py` | 9 | B.1 |
| `tests/test_realtime_webhook_skeletons.py` | 2 | D.1 |
| `tests/test_clinical_flow.py` (atualizado pra 4 stages + novos) | 6 (was 2) | B.3 + B.2 + C.1 |
| Stubs limpos em `test_admin_agents`, `test_base_agent_knowledge`, `test_agente_regulatorio`, `test_pharmacovigilance*` | — | C.2 |

**Smoke completo (2026-05-10 15:50 GMT-3):** 1504 passed, 185 skipped, 3 failed + 1 error em ~3min. As 4 falhas são todas DB-integration que requerem Postgres em `:5434` (Docker não estava up local) — sem regressões de código.

## Critérios de sucesso atingidos

- ✅ **A.2:** pool thread-safe — gunicorn multi-worker sem deadlock.
- ✅ **A.3:** `ai_audit_logs.input_payload`/`output_payload` LGPD-compliant a partir do merge. PII em texto plano fora.
- ✅ **A.4:** SECRET_KEY exigida em produção (3 pontos); ENCRYPTION_KEY exigida em produção; open redirect bloqueado.
- ✅ **B.3:** `ai_audit_logs.{clinical,treatment,report,prescription}_time_ms` deixam de ser NULL em jobs success.
- ✅ **B.2:** `estimated_cost_usd` reflete custo real quando Gemini é usado (antes era 0). `model` mostra concat tipo `"gpt-4o-mini+gemini-1.5-flash"`. **Estrutura sobreviveu até C.1** sem refactor.
- ✅ **B.1:** output do LLM passa por sanitização anti-XSS / anti-exfiltração. Audit log mantém raw pra rastreabilidade. Sanitização fail-open com `requires_review=True`.
- ✅ **C.2:** `grep mempalace|palace_room|diary_write|kg_add|self.remember` em src/ retorna só 1 hit (comentário intencional em audit_redaction.py).
- ✅ **C.1:** Paciente pára de receber dosagem sem rules engine + safety clamp + CYP450 matrix. Frontend mostra badges de safety + lista de interações.
- ✅ **C.3:** Catálogo do Prescritor documentado + 6 dívidas com Sprint alvo recomendada.
- ✅ **D.1+D.2+D.3+D.4-sub:** webhooks 501; 9 silent excepts visíveis em log; `--cov=src` ativo; staging documentado em backlog.

## Pendência única antes do fechamento operacional

⏳ **A.1 — Rotação de keys no Render dashboard** (operacional, não código).

- Rotacionar OPENAI_API_KEY + GOOGLE_API_KEY + META_WHATSAPP_KEY (e similares) via Render dashboard.
- Revogar keys antigas.
- Criar `docs/SECRETS_MANAGEMENT.md` documentando: secrets vivem no Render dashboard, nunca em arquivo local.
- Smoke pós-rotação: `/api/v1/health` + 1 chat real respondendo.

Decisão de produto pra definir janela. Memória: usuário tinha confirmado que keys atuais podiam ser rotacionadas hoje sem quebrar produção (Phase 0 Track A).

## Dívidas registradas pra Sprints 2-4

### Sprint 2 (priorizar — afetam UX/produto agora)

| Origem | Dívida | Doc/issue |
|---|---|---|
| C.1 | **AnamnesisInput não coleta `weight_kg`/`prior_cannabis_use`** → defaults em 100% dos atendimentos | `docs/BACKLOG_AGENTE_PRESCRITOR.md` Dívida 4 |
| Anchor | Plugar `prompt_registry` + tabela `ai_prompt_versions` em service.py | Q3=b adiado |
| Anchor | Paginação LIMIT/OFFSET no banco | Sprint 2 explícito |
| Anchor | Sentry / observabilidade básica | Sprint 2 explícito |
| ~~D.2.c~~ | ~~Auditar consumer frontend dos 8 endpoints com `FIXME(sprint-2)` e decidir 500 vs empty data~~ | ✅ **FECHADA na Sprint 2 Track Audit** — empty-data swallow → 5xx explícito em 11 endpoints (7 FIXMEs + 4 análogos). Pattern: OperationalError→503 `database_unavailable`; Exception→500 `internal_error`; lab_analysis com 404 explícito quando patient_id passado mas paciente inexiste. Tests: `tests/test_audit_error_handling.py`. |
| B.1 | Estender pattern 7 do `_OUTPUT_DANGER_PATTERNS` pra capturar valor das env vars | `tests/test_output_guardrail.py` FIXME |
| A.3 | Purge retroativo de logs pré-A.3 com PII em texto plano | [docs/BACKLOG_LGPD.md](../BACKLOG_LGPD.md) Dívida 1 |
| A.3 | Retention policy em `ai_audit_logs` (LGPD) | [docs/BACKLOG_LGPD.md](../BACKLOG_LGPD.md) Dívida 2 |
| A.3 | Auditoria de PII em `medical_record_entries` + `anamnesis_reports` | [docs/BACKLOG_LGPD.md](../BACKLOG_LGPD.md) Dívida 4 |
| C.1 | Cientifico citar evidência da `final_dosage` (não do treatment_plan draft) | `docs/BACKLOG_AGENTE_PRESCRITOR.md` Dívida 6 |

### Sprint 3 (clínico — exige revisão médica externa)

| Origem | Dívida | Doc |
|---|---|---|
| C.3 | Expandir `CONDITION_PROTOCOLS` (top 10: glaucoma, Alzheimer, ELA, anorexia em câncer, espasticidade pós-AVC, Tourette, Huntington, fibrose cística, Dravet, AIDS-wasting) | `docs/BACKLOG_AGENTE_PRESCRITOR.md` Dívida 1 |
| C.3 | Expandir `CYP450_INTERACTIONS` (top 25 drugs catalogados; recomenda migrar pra Drug Interaction Database) | `docs/BACKLOG_AGENTE_PRESCRITOR.md` Dívida 2 |
| C.3 | Granularidade safety clamp (Child-Pugh hepática, clearance renal, IMC, sexo, polifarmacia, comorbidade cardio) | `docs/BACKLOG_AGENTE_PRESCRITOR.md` Dívida 3 |
| A.3 | Rotação SECRET_KEY exige re-encryption schema (versioned ENCRYPTION_KEY) | [docs/BACKLOG_LGPD.md](../BACKLOG_LGPD.md) Dívida 3 |

### Sprint 4 (eval harness + endurecimento)

| Origem | Dívida | Doc |
|---|---|---|
| B.1 | Eval harness com corpus real → calibrar threshold da Camada 4 e considerar promover de "sanitiza + flag" para "bloqueio total" em alta confidence | inline em `sprint_1_B.md` |
| C.1 | `safety_clamp_applied` heurística vs comparação raw vs clamped exata (refactor de `run_prescriber`) | `docs/BACKLOG_AGENTE_PRESCRITOR.md` Dívida 5 |

### Sem prazo definido (gatilho operacional)

- Staging environment quando deploy quebrar prod ou demo investidor (`docs/STAGING_BACKLOG.md`).
- `--cov-fail-under=N` em pytest.ini quando baseline de cobertura estiver medida (D.3).
- Migração `gemini-1.5-flash` → `gemini-2.5-flash` antes de jun/2026 (`docs/BACKLOG_AI_MIGRATION.md`).
- C6 (agentes ingerindo conhecimento durante atendimento) e C7 (extração de conhecimento agregado) — `docs/22_EXECUTIVE_BACKLOG.md` Frente C.

## Lições aprendidas

1. **Phase 0 evitou conflitos sérios.** Track A descobriu que `SECRET_KEY` aparecia em 3 pontos (não 1) — o anchor file só listava `config.py:25`. Corrigir os 3 simultaneamente fechou a vulnerabilidade real.
2. **Estruturas extensíveis bem desenhadas pagam dividendo.** B.2 entregou `tokens_per_stage` extensível; C.1 plugou `"prescription"` sem 1 linha de refactor em service.py.
3. **Single-point-of-intervention para preocupações cross-cutting.** A.3 sanitizou no repository, NÃO nos call sites — C.1 ganhou PII protection no `prescription_result` automaticamente.
4. **Numerações em anchor file ficam desatualizadas.** Anchor disse migrations 124-125 mas última real era 042. Phase 0 sempre verifica filesystem real.
5. **Memory cache pode mentir.** Hooks injetaram observações falsas dizendo que `service.py` já estava wired pra `prescription_result` e que `ai_audit_logs` já tinha colunas Prescritor — ambas falsas. Verificar arquivos reais sempre.
6. **Decisão UX explícita do coordenador economiza retrabalho.** C.1.4 — display em `/atendimentos/[id]` standalone (não em `/med/prescricao/*`) — foi decidida antes da Phase 0 do frontend e evitou refactor de `prescription_contract`.

## Próximo passo: Sprint 2

**Foco recomendado** (ordem de prioridade derivada das dívidas acima):

1. **Estender `AnamnesisInput` + widget de triagem** pra coletar peso, altura, uso prévio de cannabis. Remove o badge "defaults conservadores" que aparece em 100% dos atendimentos hoje. (Dívida C.4 — alta prioridade clínica.)
2. **Plugar `prompt_registry` + `ai_prompt_versions`** (Q3=b adiado da Sprint 1).
3. **Paginação LIMIT/OFFSET** no banco — endpoints sem paginação são bomba-relógio com volume real.
4. **Sentry** — observabilidade básica antes de pacientes piloto chegarem em produção.
5. ~~**Auditar 8 endpoints com `FIXME(sprint-2)`** — decidir 500 vs empty data caso a caso (D.2.c).~~ → ✅ resolvido em Sprint 2 Track Audit (11 endpoints migrados pra 5xx explícito).
6. **Purge retroativo de logs pré-A.3 + retention policy** (LGPD Dívidas 1+2).

## Encerramento

**Sprint 1 fechada — 4 tracks, 9 PRs, 11 sub-tarefas mergeadas.**

- Track A (security+LGPD): pool thread-safe, PII redaction estrutural em audit logs, SECRET_KEY/ENCRYPTION_KEY hardening, next_url validation. **Pendente:** A.1 rotação keys no Render (operacional).
- Track B (guardrails+cost): Camada 4 viva, Gemini pricing + cost por stage, `timings_ms` populado.
- Track C (architectural surgery): Prescritor no flow + MemPalace 100% extirpado + backlog Prescritor catalogado.
- Track D (tactical): webhooks 501, logging em 9 silent excepts, `--cov=src`, staging em backlog.

**Próximo:** Sprint 2 — estender AnamnesisInput, prompt_registry, paginação, Sentry, FIXMEs do D.2.c, purge retroativo LGPD.
