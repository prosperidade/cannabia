# Sprint 3 — Track Obs-Harden (Sentry Hardening)

Fecha as dividas deferidas pela Sprint 2 Track Obs (`sprint_2_Obs.md`).

A Sprint 2 entregou Sentry plugado em prod, mas com tres frouxidoes
deliberadas pra nao bloquear rollout:

1. SOFT-FAIL no DSN: app subia sem Sentry se `SENTRY_DSN` ausente.
2. `traces_sample_rate=0.0`: zero performance traces.
3. `include_local_variables=False`: locals em traceback descartados.

A Sprint 3 endurece os tres pontos agora que o Sentry foi validado em
prod e a sanitizacao PII (Track A.3 — `sanitize_clinical_payload`) ficou
estavel.

## Status

- Branch: `feat/sprint-3-Obs-harden`
- Cross-link: <- `sprint_2_Obs.md` (link bilateral).
- HEAD-base: `e2f9c39` (post-Sprint 2 consolidation).

## Decisoes do Coordenador (Sprint 3)

| Pergunta | Decisao |
|----------|---------|
| Q-OH-1 (DSN ausente em prod) | RAISE direto, pattern A.4 (`_get_secret_key_or_fail`). Mensagem instrutiva apontando Render dashboard. Dev path inalterado (silent). |
| Q-OH-2 (performance traces) | `traces_sample_rate=0.1` (10% piloto Sprint 3 — quer dados pra calibrar Sprint 4). Override via env `SENTRY_TRACES_SAMPLE_RATE` com clamp 0..1. |
| Q-OH-3 (locals em traceback) | `include_local_variables=True` SEMPRE (dev/staging/prod). Sanitizacao em `_sentry_before_send` (walk recursivo em `frames[].vars`) e' a defesa, nao `FLASK_ENV`. |
| Q-OH-4 (sanitizacao frames vars) | Walk recursivo full reusando `sanitize_clinical_payload` (Track A.3) — fail-safe, ja existia, zero codigo novo. |
| Q-OH-5 (documentacao) | Doc novo (este) + cross-link bilateral com `sprint_2_Obs.md`. |

## Diff Pattern Soft (Sprint 2) → Hard (Sprint 3)

### `src/config.py::_get_sentry_config`

Sprint 2 (soft):

```python
if not dsn:
    if is_production:
        _logger.error("SENTRY_DSN ausente em producao — app sobe sem ...")
    else:
        _logger.debug("SENTRY_DSN ausente em dev — Sentry off (esperado).")
    return None
```

Sprint 3 (hard):

```python
if not dsn:
    if is_production:
        raise RuntimeError(
            "SENTRY_DSN env var required in production. "
            "Setar no Render dashboard antes do deploy."
        )
    _logger.debug("SENTRY_DSN ausente em dev — Sentry off (esperado).")
    return None
```

Dev path inalterado. Prod: alinha com pattern A.4 — chave critica
ausente em prod e' falha-rapido, nao degradar-silenciosamente.

### `src/infra/observability.py::init_sentry`

Sprint 2:

```python
traces_sample_rate=0.0,        # Q-Obs-3: performance off Sprint 2
include_local_variables=False, # Q-Obs-4: PII em locals = LGPD breach
```

Sprint 3:

```python
traces_sample_rate=config.get("traces_sample_rate", 0.1),
                # Q-OH-2: vem do config dict (env override),
                # default 0.1 (10% piloto Sprint 3)
include_local_variables=True,
                # Q-OH-3: locals valiosos pra debug, sanitizados em
                # _sentry_before_send via walk recursivo em
                # frames[].vars (sanitize_clinical_payload)
```

### `render.yaml`

Adicionado:

```yaml
# Sprint 3 Track Obs-Harden — SENTRY_DSN agora OBRIGATORIO em prod
- key: SENTRY_TRACES_SAMPLE_RATE
  value: "0.1"
```

## ⚠ Checklist Pre-Deploy

**ANTES** de fazer `git push origin main` (deploy automatico):

- [ ] Confirmar que `SENTRY_DSN` esta setado no Render dashboard
      (service `cannabia-api` → Environment → secret).
- [ ] DSN valido (formato `https://<key>@o<org>.ingest.<region>.sentry.io/<project>`).
- [ ] Testar que `SENTRY_ENVIRONMENT=production` segue presente.
- [ ] (Opcional) Ajustar `SENTRY_TRACES_SAMPLE_RATE` se quota Sentry
      apertar — `0.05` ou `0.02` em caso de alto volume.

**Se DSN ausente no push:** `preDeployCommand` (`run_migrations`) tambem
importa `src.config`, entao a propria fase de migration vai raise. Deploy
falha early — bom, mas voce perde 1-2 min de build pra descobrir.
Preferivel confirmar antes.

## Trade-offs: `traces_sample_rate=0.1` vs Quota Sentry

Sentry free tier: **10k transactions/mes**.

| Volume HTTP/mes | Sample rate | Transactions/mes | Fit free tier? |
|----------------:|------------:|-----------------:|:---------------|
| 10k             | 1.0 (100%)  | 10k              | ✅ Limite exato |
| 50k             | 0.2 (20%)   | 10k              | ✅ Limite exato |
| 100k            | 0.1 (10%)   | 10k              | ✅ Limite exato |
| 200k            | 0.05 (5%)   | 10k              | ✅ Folga zero  |
| 500k            | 0.02 (2%)   | 10k              | ✅ Folga zero  |

Sprint 3 escolheu `0.1` partindo de premissa conservadora: ~100k
requests/mes esperado em piloto (clinicas pequenas). Se trafego subir,
**reduzir via Render dashboard** (`SENTRY_TRACES_SAMPLE_RATE`) sem
precisar de redeploy de codigo.

Sprint 4 deve calibrar com base em telemetria real (transactions/dia
no Sentry dashboard).

Doc oficial:
<https://docs.sentry.io/concepts/key-terms/tracing/trace-view/#span-aggregations>

## Politica `include_local_variables=True` + Sanitizacao em Frames

Sprint 2 conservou `=False` por medo de PII vazar via locals. Sprint 3
descobre que isso era over-engineering: `_sentry_before_send` ja fazia
walk full em `exception.values[i].stacktrace.frames[j].vars` (linhas
94-113 em `src/infra/observability.py`) reusando
`sanitize_clinical_payload`. O `=False` so escondia debug uteis sem
ganho de seguranca real — locals viriam vazios, mas se viessem
populados seriam sanitizados de qualquer forma.

Pattern: **defense in depth** com sanitizacao explicita >
black-box-disable.

### Defesa por Camadas (recap LGPD-Critical)

1. **`send_default_pii=False`** — Sentry nativo nao captura cookies,
   headers `Authorization`, IP do request.
2. **`include_local_variables=True`** — Sprint 3 expoe locals em
   traceback (era off Sprint 2). Util pra debug.
3. **`_sentry_before_send` walk** — sanitiza recursivamente:
   - `request.data`
   - `extra`
   - `breadcrumbs[].data` (formato dict ou lista)
   - `exception.values[].stacktrace.frames[].vars`  ← **defesa pra Q-OH-3**
4. **Fail-safe** — se sanitizer raise, DROPA event (`return None`).
   LGPD-critical: perder telemetria > vazar PII em DSN externo.

## Testes

`tests/test_observability.py` cresceu de 4 → 8:

| Teste | Cobre |
|-------|-------|
| `test_sentry_off_when_dsn_missing` (adaptado) | init_sentry(None) no path dev |
| `test_before_send_redacts_clinical_pii` | request.data + extra |
| `test_before_send_drops_event_on_sanitization_failure` | fail-safe |
| `test_tag_request_handles_missing_g_attrs` | rotas publicas |
| `test_sentry_config_raises_in_prod_without_dsn` (NOVO Q-OH-1) | hard fail |
| `test_sentry_config_soft_in_dev_without_dsn` (NOVO) | dev intocado |
| `test_traces_sample_rate_from_env` (NOVO Q-OH-2) | env override + clamp |
| `test_before_send_sanitizes_frames_vars` (NOVO Q-OH-3) | frames vars walk |

## Arquivos Tocados

- `src/config.py` — `_get_sentry_config`: raise prod + traces_sample_rate.
- `src/infra/observability.py` — `init_sentry`: traces do config + locals=True.
- `render.yaml` — `SENTRY_TRACES_SAMPLE_RATE=0.1` + comentario DSN-obrigatorio.
- `tests/test_observability.py` — 4 novos + 1 adaptado.
- `docs/sprints/sprint_3_Obs_Harden.md` — este doc.
- `docs/sprints/sprint_2_Obs.md` — secao de cross-link no fim.

## Dividas Pra Sprint 4+

- `/admin/debug/sentry-test` endpoint admin-only pra smoke test seguro
  (divida remanescente da Sprint 2).
- Calibrar `traces_sample_rate` com base em volume real medido pos
  primeiro mes de produ.
- `sentry_sdk.set_release()` integrado com versionamento git (auto-tag
  no deploy).
- Source maps frontend (Next.js) — track separada `Obs-FE`.

## Cross-Link

- Sprint 2 base (introducao Sentry): [`sprint_2_Obs.md`](./sprint_2_Obs.md)
