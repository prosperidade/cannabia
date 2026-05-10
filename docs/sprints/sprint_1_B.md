# Sprint 1 — Track B (Guardrails + Cost honesto) — Fechamento

**Branch base:** `main` @ `f74cde9` (post-Track D merge).
**Status:** completo após 3 PRs mergeados.
**Esforço executado:** ~5h (estimativa Phase 0: 4-5h).

## Sub-tarefas e PRs

| Sub-tarefa | Branch | Commit | PR | Status |
|---|---|---|---|---|
| **B.3** — Popular `timings_ms` via `time.perf_counter()` em clinical_flow | `feat/sprint-1-B-guardrails-cost` | `7b2059e` | #20 | ✅ mergeado |
| **B.2** — Cost honesto por stage + Gemini pricing + AI migration backlog | `feat/sprint-1-B-2-cost-honesto` | `e24162c` | #21 | ✅ mergeado |
| **B.1** — Plug Camada 4 (output guardrail) em service.py + helper recursivo | `feat/sprint-1-B-1-camada4-output-guardrail` | (este PR) | TBD | 🔄 em PR |

## Decisões de Phase 0 confirmadas pelo coordenador

1. **B.3 solução (a):** `time.perf_counter()` manual em volta de cada `with measure(...)` — não toca `src/infra/metrics.py` (fora do escopo). 6 linhas, isolado.

2. **B.2 escopo expandido:** ao adicionar Gemini pricing, descobrimos que `service.py:155-159` calculava custo agregado usando único `model="gpt-4o-mini"` para soma de tokens dos 3 stages. Quando RAG ativo (caminho normal), os tokens do Gemini eram contados como se fossem OpenAI — cost subnotificado/distorcido. Track B.2 corrige isso retornando `tokens_per_stage` extensível e somando `calculate_cost` por stage com modelo correto.

3. **B.2 estrutura extensível confirmada:** `tokens_per_stage = {stage_name: {"model": str, "tokens": {"input": int, "output": int}}}`. Track C adiciona entry `"prescription"` sem mudar consumer.

4. **B.1 helper recursivo nos string-leaves:** confirmado. Em vez de `json.dumps + regex.sub + parse` (corrompe estrutura JSON), aplica `sanitize_output` em cada string-leaf preservando tipos.

5. **B.1 calibração progressiva:** confirmado. Camada 4 **NÃO bloqueia** output detectado como suspeito — sanitiza + sinaliza via `_guardrail_output.requires_review=True`. Sprint 4 (eval harness) endurece com base em corpus real.

6. **B.1 sem re-validação Pydantic pós-sanitize:** confirmado. `model_dump()` já foi feito antes do retorno; sanitização preserva tipos.

7. **Pricing Gemini com comentário legacy:** valores `$0.075/1M` input + `$0.30/1M` output usados; registrada dívida de migração pra `gemini-2.5-flash` antes de jun/2026.

## Mudanças por arquivo (consolidado das 3 PRs)

| Arquivo | Mudança | Sub-tarefa |
|---|---|---|
| `src/ai/clinical_flow.py` | `time` import + 3 captures `time.perf_counter()` + return `timings_ms` (B.3); + return `tokens_per_stage` (B.2) | B.3, B.2 |
| `src/ai/pricing.py` | + entry `gemini-1.5-flash` ($0.075/1M input, $0.30/1M output) com comentário legacy | B.2 |
| `src/ai/service.py` | Cost agregado por stage + `effective_model` concat (B.2); `apply_to_output_dict` + `_guardrail_output` flag (B.1) | B.2, B.1 |
| `src/ai/guardrails.py` | + `_sanitize_string_leaves(obj)` recursivo + `apply_to_output_dict(dict, config)` helper | B.1 |
| `tests/test_clinical_flow.py` | +7 asserts sobre `timings_ms` e `tokens_per_stage` | B.3, B.2 |
| `tests/test_pricing.py` | Novo — 7 testes (gpt baseline, gemini baseline, sanity gemini=gpt/2, modelo desconhecido, zero/None tokens, tabela completa) | B.2 |
| `tests/test_output_guardrail.py` | Novo — 9 testes (legitimo passa, exfiltration sanitizado, lista aninhada, script tag, preserva tipos, zero-width chars, gap conhecido, defensive não-dict, sanitize_output independente) | B.1 |
| `docs/BACKLOG_AI_MIGRATION.md` | Novo — dívida `gemini-1.5-flash` → `gemini-2.5-flash` pré-jun/2026 | B.2 |
| `docs/sprints/sprint_1_B.md` | Este arquivo | encerramento |

## Testes

- B.3: 2/2 verde (`tests/test_clinical_flow.py`)
- B.2: 9/9 verde (`tests/test_clinical_flow.py` + `tests/test_pricing.py`)
- B.1: 9/9 verde (`tests/test_output_guardrail.py`)
- **Total Track B: 18/18 verde** (~14s)

## Critérios de sucesso atingidos

- ✅ **B.3:** `ai_audit_logs.{clinical_time_ms, treatment_time_ms, report_time_ms}` deixam de ser `NULL` em jobs success após merge.
- ✅ **B.2:** `ai_audit_logs.estimated_cost_usd` reflete custo real quando Gemini é usado (antes era 0 ou underestimado). `ai_audit_logs.model` mostra concat tipo `"gpt-4o-mini+gemini-1.5-flash"`.
- ✅ **B.1:** Output do LLM passa por sanitização anti-XSS / anti-exfiltração antes de chegar ao paciente. Audit log mantém raw pra rastreabilidade. Sanitização é fail-open (não bloqueia, sinaliza com `requires_review=True`).

## Gap conhecido descoberto durante B.1 (registrado como dívida)

🟡 **Pattern 7 do `_OUTPUT_DANGER_PATTERNS`** ([src/ai/guardrails.py:352](src/ai/guardrails.py#L352)) só captura nome da env var, não o valor:
```python
r"(OPENAI_API_KEY|GOOGLE_API_KEY|DATABASE_URL|SECRET_KEY)\s*[:=]"
```
Para `OPENAI_API_KEY=sk-proj-abc...`, sanitiza `OPENAI_API_KEY=` para `[REDACTED]` mas deixa `sk-proj-abc...` no output. Pattern 6 (`api_key|password|secret_key|token`) já captura nome+valor — basta estender pattern 7 com `\s*['\"]?\w{8,}` análogo. **FIXME(sprint-2)** em [tests/test_output_guardrail.py:test_known_regex_gap_env_var_name_pattern_leaves_value](tests/test_output_guardrail.py).

## Pendências / dívidas explícitas registradas

- **Sprint 2:** plugar `prompt_registry` + tabela `ai_prompt_versions` em service.py (não é Track B, mas não esquecer).
- **Sprint 2:** estender pattern 7 do `_OUTPUT_DANGER_PATTERNS` pra capturar valor das env vars.
- **Sprint 4:** eval harness com corpus real → calibrar threshold da Camada 4 e considerar promover de "sanitiza + flag" para "bloqueio total" em casos de alta confidence.
- **Antes de jun/2026:** migrar `gemini-1.5-flash` → `gemini-2.5-flash` (ver [docs/BACKLOG_AI_MIGRATION.md](docs/BACKLOG_AI_MIGRATION.md)).

## Sequenciamento de merge

| Track | Ordem doc | Status |
|---|---|---|
| D | 1º (tactical) | ✅ Mergeado (PR #19) |
| A | 2º (security/LGPD) | ⏳ chat dedicado |
| B | **3º** (este) | ✅ B.3+B.2 mergeados, B.1 em PR |
| C | 4º (architectural) | ⏳ aguardando B inteiro |

Track C parte do `clinical_flow.py` com `timings_ms` + `tokens_per_stage` populados. C deve preservar ambos no return e adicionar entries para a 4ª etapa (Prescritor):
- `timings_ms.prescription`
- `tokens_per_stage.prescription = {"model": "gpt-4o-mini", "tokens": {...}}`

Sem isso, o cost do Prescritor entra distorcido no audit (igual ao bug que B.2 corrigiu pro Gemini).

## Observações pra Track A

Track A vai mexer em `src/ai/service.py` para sanitizar PII em `input_payload`/`output_payload` antes de `save_ai_audit_log`. **Conflito esperado** com B.1 e B.2 que também tocam nessa função (no caminho success). Mitigação: A parte de main pós-B mergeada e adapta o `output_payload=result` (B.1 deixou raw aqui — A precisa sanitizar PII separadamente).
