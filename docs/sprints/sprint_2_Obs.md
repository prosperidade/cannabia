# Sprint 2 — Track Obs (Sentry Observability)

Plug Sentry SDK em producao com sanitizacao rigorosa de PII (LGPD-critical).

## Status

- Branch: `feat/sprint-2-Obs-sentry`
- Coordenador respondeu Q-Obs-1..5 (decisoes abaixo).
- Greenfield: sentry-sdk[flask]>=2.0.0 adicionado a requirements.txt.

## Decisoes do Coordenador

| Pergunta | Decisao |
|----------|---------|
| Q-Obs-1 (DSN ausente em prod) | SOFT — log error mas app sobe sem Sentry. Sprint 3+ pode endurecer. |
| Q-Obs-2 (denylist PII) | DEFENSE IN DEPTH: `send_default_pii=False` + `before_send` reusando `sanitize_clinical_payload`. |
| Q-Obs-3 (performance traces) | `traces_sample_rate=0.0` — caro, valor baixo Sprint 2. |
| Q-Obs-4 (locals em traceback) | `include_local_variables=False` (era `with_locals` em SDK 1.x) — locals podem vazar PII. |
| Q-Obs-5 (LoggingIntegration) | `event_level=ERROR`, `level=WARNING` (warning vira breadcrumb). |

## Arquivos Tocados

- `requirements.txt` — adiciona `sentry-sdk[flask]>=2.0.0`.
- `src/config.py` — helper `_get_sentry_config()` (soft em prod).
- `src/infra/observability.py` — novo modulo: `init_sentry`, `tag_request`,
  `_sentry_before_send`.
- `src/app.py` — `init_sentry` no topo de `create_app`, `tag_request(g)`
  no `before_request`.
- `render.yaml` — envs `SENTRY_DSN` (sync:false), `SENTRY_ENVIRONMENT`,
  `SENTRY_SAMPLE_RATE`.
- `tests/test_observability.py` — 4 tests cobrindo soft-off, redact,
  fail-drop, tag defensivo.

## Como Configurar em Producao

### 1. Criar projeto Sentry novo

1. Acesse <https://sentry.io/> e crie/escolha uma organizacao.
2. New Project → plataforma `Python / Flask` → nome `cannabia-api-prod`.
3. Sentry mostrara um DSN do tipo:
   `https://abc123@o12345.ingest.us.sentry.io/67890`
4. Copie esse DSN.

Doc oficial: <https://docs.sentry.io/platforms/python/integrations/flask/>

### 2. Colar DSN no Render dashboard

`render.yaml` declara `SENTRY_DSN` com `sync: false` — ou seja, o valor
NAO vem do repo. Configure manualmente:

1. Render dashboard → service `cannabia-api` → Environment.
2. Adicione var `SENTRY_DSN` com o valor copiado do Sentry.
3. Save → Render reinicia o service automaticamente.

`SENTRY_ENVIRONMENT=production` e `SENTRY_SAMPLE_RATE=1.0` ja vem do
render.yaml — ajuste no dashboard se quiser sample rate menor (ex:
`0.1` pra capturar 10% dos errors em servicos de alto volume).

### 3. Verificar a integracao

Sprint 2 NAO criou um endpoint de teste dedicado (`/debug/sentry-trigger`).
Pra verificar:

- Cause um error real (ex: HTTP 500 em rota com bug conhecido) e
  confira se aparece no Sentry dashboard em ate 1 min.
- Sprint 3+ pode adicionar endpoint admin-only `/admin/debug/sentry-test`
  pra trigger seguro.

Se DSN errado/quebrado: app sobe, log local mostra
`"Falha ao inicializar Sentry: ..."` mas requests continuam funcionando.

## Politica de PII (LGPD-Critical)

Defesa em camadas:

1. **Camada Sentry nativa**: `send_default_pii=False` desabilita captura
   de cookies, headers `Authorization`, IP, etc.
2. **Camada `include_local_variables=False`**: stacktrace frames NAO
   carregam variaveis locais (que podem ter `patient_name`, `cpf`, etc.).
   (Em sentry-sdk 1.x esse parametro chamava `with_locals`.)
3. **Camada `before_send` custom**: reusa `sanitize_clinical_payload`
   (Track A.3) em `request.data`, `extra`, `breadcrumbs.values[].data`,
   e `exception.values[].stacktrace.frames[].vars` se algum sobrar.
4. **Fail-safe**: se `_sentry_before_send` quebrar internamente, DROPA
   o event (`return None`) — preferimos perder telemetria do que vazar
   PII em DSN externo.

## Tags Anexadas (forensics)

`tag_request(g)` no `before_request` anexa:

- `request_id` — correlaciona Sentry event com logs JSON locais.
- `user.id` — permite filtrar errors por usuario afetado.
- `clinic_id` — multi-tenant: identifica clinica afetada.
- `tenant_id` — multi-tenant: identifica tenant.

Tudo via `getattr(g, attr, None)` — rotas publicas sem auth/tenant
nao quebram.

## Dividas Pra Sprint 3+

- `/debug/sentry-trigger` admin-only pra smoke test seguro.
- Considerar `traces_sample_rate=0.05` pra performance baseline (decisao
  Q-Obs-3 pode mudar quando volume justificar custo).
- Hard-fail em prod se DSN ausente (decisao Q-Obs-1 deliberadamente
  soft Sprint 2 pra nao bloquear rollout).
- Source maps / release tracking via `sentry_sdk.set_release()`.

## ✅ Hardening Sprint 3 → ver [`sprint_3_Obs_Harden.md`](./sprint_3_Obs_Harden.md)

Sprint 3 Track Obs-Harden fecha as 3 dividas principais herdadas:

1. **Q-Obs-1 soft-fail → Q-OH-1 hard-fail**: SENTRY_DSN ausente em prod
   agora raise (`_get_sentry_config`).
2. **Q-Obs-3 traces=0.0 → Q-OH-2 traces=0.1**: 10% piloto via env
   `SENTRY_TRACES_SAMPLE_RATE` com clamp 0..1.
3. **Q-Obs-4 locals=False → Q-OH-3 locals=True**: sanitizacao em
   `_sentry_before_send` (walk em `frames[].vars`) e' defesa suficiente.

Detalhes completos, side-by-side diff, checklist pre-deploy e trade-offs
de quota Sentry em [`sprint_3_Obs_Harden.md`](./sprint_3_Obs_Harden.md).
