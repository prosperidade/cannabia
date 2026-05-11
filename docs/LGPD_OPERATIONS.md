# Runbook LGPD — Operacoes em `ai_audit_logs`

> Sprint 2 Track LGPD. Codigo entregue + cron deployado. **Production run espera OK juridico** (ver aviso abaixo).

---

## ⚠️ AVISO — DEPENDE DE OK JURIDICO

Os prazos de retencao definidos abaixo (90d / 365d / 5y) sao **defensaveis tecnicamente** mas **NAO foram revisados pela area juridica** ate o merge desta PR.

- O **Render Cron Job `cannabia-audit-retention`** eh agendado e roda diariamente, MAS comeca **DESATIVADO** via kill switch `LGPD_PURGE_ENABLED=false` (default em `render.yaml`). Enquanto a flag for false, o cron loga "DESATIVADO (no-op)" e retorna 0 — zero efeito em DB. Quando o juridico aprovar, **vire `LGPD_PURGE_ENABLED=true` no Render dashboard** (Environment > edit env var) — proximo run do cron passa a executar.
- O **purge retroativo** (`scripts/purge_audit_pii_pre_a3.py`) NAO roda em producao automaticamente — eh manual.
- **Antes de ligar a flag** (ou de rodar o purge manual em prod), o coordenador deve revisar:
  - Prazos de retencao com area juridica + DPO.
  - Politica de archive cleanup (5y).
  - Processo de snapshot/rollback documentado neste runbook.

Alternativa pra adiar o cron alem do kill switch: **suspender o service no Render dashboard** (efeito equivalente, mas exige re-enable manual).

---

## Visao geral

3 mecanismos cooperam:

| Mecanismo | Tipo | Frequencia | Tabelas afetadas |
| --- | --- | --- | --- |
| `sanitize_clinical_payload` (A.3) | Forward sanitization | Cada gravacao | `ai_audit_logs` (write path) |
| `scripts/purge_audit_pii_pre_a3.py` | Backfill manual | 1x ate "limpar" pre-A.3 | `ai_audit_logs` (UPDATE in-place) |
| `scripts/retention_audit_logs.py` | Cron diario | 04:00 UTC | `ai_audit_logs` -> `ai_audit_logs_archive` -> DROP |

Tabelas auxiliares (Sprint 2 LGPD):
- `ai_audit_purge_events` — audit trail de cada execucao (started/finished, contagens, dry_run).
- `ai_audit_purge_processed_ids` — dedup pra resume support do purge retroativo.
- `ai_audit_logs_archive` — cold storage com `archived_at`. Cleanup automatico apos 5y.
- `ai_audit_logs_pre_redact_backup_<YYYYMMDD>` — snapshot table criada pelo purge. **TTL 30d, drop manual.**

---

## Step-by-step: purge retroativo (1x)

### Pre-requisitos

- Migrations 044 e 045 aplicadas (auto via `preDeployCommand` do `cannabia-api`).
- OK juridico documentado (issue/PR/email arquivado).
- Janela de baixo trafego acordada (recomendado: madrugada UTC).
- Coordenador com acesso ao Render Shell + DB read/write.

### Etapa 1 — Snapshot manual no Render dashboard

Antes de qualquer mutacao, criar snapshot do DB pelo painel do Render:

1. Render dashboard -> `cannabia-db` -> **Backups** -> "Create snapshot".
2. Nome sugerido: `pre-lgpd-purge-YYYYMMDD`.
3. Aguardar status "Completed" (alguns minutos).

> Snapshot do Render eh **independente** da snapshot table criada pelo script. Os dois servem propositos diferentes (DB inteiro vs. apenas a tabela alvo). **Manter ambos.**

### Etapa 2 — Dry-run

```bash
# Render Shell do service cannabia-api (mesmo env do Postgres)
python -m scripts.purge_audit_pii_pre_a3 --dry-run
```

Output esperado:
- `Total estimado de rows pendentes: N`
- `[batch 1] scanned=B updated=B failed=0`
- `[dry-run] saindo apos primeiro batch`

**Validar:** `N` esta dentro da ordem de grandeza esperada (rodar o COUNT manual da Divida 1 do `BACKLOG_LGPD.md` pra comparar).

### Etapa 3 — Commit run

```bash
python -m scripts.purge_audit_pii_pre_a3 \
  --commit \
  --batch-size 500 \
  --max-batches 200
```

Variantes:
- Restringir a 1 clinica: `--clinic-id 42`.
- Cutoff custom: `--cutoff '2026-05-10T17:00:00+00:00'` (default).

O script:
1. Cria snapshot table `ai_audit_logs_pre_redact_backup_<YYYYMMDD>` (idempotente).
2. Insere row em `ai_audit_purge_events` (started_at, dry_run=FALSE).
3. Loop batched: SELECT -> sanitize -> UPDATE -> insert em `processed_ids`.
4. UPDATE event row a cada batch (rows_scanned/updated/failed).
5. SET finished_at no fim.

### Etapa 4 — Validacao

```sql
-- Evento mais recente
SELECT * FROM ai_audit_purge_events ORDER BY id DESC LIMIT 1;

-- Spot-check: PII residual em rows pre-cutoff?
SELECT id, request_id, created_at
FROM ai_audit_logs
WHERE created_at < '2026-05-10 17:00:00+00'
  AND (input_payload::text ~ '\d{3}\.\d{3}\.\d{3}-\d{2}'
    OR output_payload::text ~ '\d{3}\.\d{3}\.\d{3}-\d{2}'
    OR input_payload::text ~ '[a-zA-Z0-9._%-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
LIMIT 20;
```

Se a query retornar rows: rodar novamente (idempotente, so pega rows nao processadas).

### Etapa 5 — Drop snapshot table apos 30d

```sql
-- Listar snapshots existentes
SELECT tablename FROM pg_tables
WHERE tablename LIKE 'ai_audit_logs_pre_redact_backup_%'
ORDER BY tablename DESC;

-- Apos 30d, drop manual
DROP TABLE ai_audit_logs_pre_redact_backup_20260510;
```

> **Alerta manual no calendario do coordenador.** Sem alerta automatico — a snapshot table sobrevive ate alguem deletar.

---

## Politica de retention (cron diario)

Render Cron Job `cannabia-audit-retention` (definido em `render.yaml`):

```yaml
schedule: "0 4 * * *"   # 04:00 UTC = 01:00 BRT
startCommand: python -m scripts.retention_audit_logs
```

### Regras

| Tipo de log | Prazo no hot table | Onde editar |
| --- | --- | --- |
| Detail (`status` comum: `success`, etc.) | 90 dias | `LGPD_AUDIT_RETENTION_DAYS_DETAIL` |
| Critical (`status IN ('security_blocked','error')`) | 365 dias | `LGPD_AUDIT_RETENTION_DAYS_CRITICAL` |
| Archive cleanup | 5 anos (1825 dias) | `LGPD_AUDIT_ARCHIVE_RETENTION_DAYS` |

Definicoes em `render.yaml` no service `cannabia-audit-retention`. Para alterar:
1. Editar `render.yaml` na main.
2. Render redeploy automatico do cron (next run usa novo valor).
3. Documentar mudanca aqui + linkar para o ticket juridico que aprovou.

### Comportamento

A cada execucao:
1. Move pra `ai_audit_logs_archive` rows que ultrapassaram o limiar (com `archived_at = NOW()`).
2. DELETE em `ai_audit_logs` dos mesmos IDs (CTE single-tx — race com inserts novos eh seguro: filtro por `created_at` exclui rows recem-criados).
3. DELETE em `ai_audit_logs_archive` rows com `archived_at < NOW() - 5y`.
4. Insere row em `ai_audit_purge_events` com `executor_host='cron'`.

### Observabilidade

```sql
-- Ultimas 7 execucoes do cron
SELECT id, started_at, finished_at, rows_updated, rows_failed, error_summary
FROM ai_audit_purge_events
WHERE executor_host = 'cron'
ORDER BY id DESC
LIMIT 7;
```

Se `rows_failed > 0` ou `finished_at IS NULL` apos 1h da execucao agendada: investigar logs do cron no Render.

---

## Rollback

### Caso 1: dry-run mostrou comportamento errado

Sem rollback necessario — dry-run nao toca DB.

### Caso 2: commit run aplicou sanitize errado

Restaurar da snapshot **table** local (mais rapido, mais cirurgico):

```sql
-- Restaura input/output_payload das rows tocadas naquele commit
UPDATE ai_audit_logs t
SET input_payload  = b.input_payload,
    output_payload = b.output_payload
FROM ai_audit_logs_pre_redact_backup_20260510 b
WHERE t.id = b.id
  AND t.id IN (
    SELECT audit_log_id FROM ai_audit_purge_processed_ids
    WHERE purge_event_id = <event_id_problematico>
  );

-- Limpa marcador de processed (pra pode re-rodar com sanitize corrigido)
DELETE FROM ai_audit_purge_processed_ids
WHERE purge_event_id = <event_id_problematico>;
```

### Caso 3: corrupcao maior

Restaurar do snapshot **do Render** (passo 1 do purge). Operacao pesada — coordenar com SRE.

### Caso 4: cron de retention apagou rows que nao devia

```sql
-- Resgatar do archive
INSERT INTO ai_audit_logs
SELECT id, patient_id, clinic_id, request_id, user_id, endpoint,
       input_payload, output_payload, status, error_message, model,
       prompt_version, prompt_hash, input_tokens, output_tokens,
       total_tokens, clinical_time_ms, treatment_time_ms,
       report_time_ms, total_time_ms, created_at, estimated_cost_usd,
       prescription_time_ms, prescription_input_tokens,
       prescription_output_tokens
FROM ai_audit_logs_archive
WHERE id IN (...);

-- Remove do archive
DELETE FROM ai_audit_logs_archive WHERE id IN (...);
```

> Nota: o INSERT acima omite `archived_at` propositalmente (so existe no archive). Ajustar lista de colunas se schema evoluir — sempre derivar de `\d ai_audit_logs` antes de copiar.

---

## Checklist pre-merge da Sprint 2 LGPD

- [ ] Migrations 044 e 045 revisadas + testadas em local.
- [ ] Tests passando: `pytest tests/test_audit_redaction.py tests/test_purge_script.py tests/test_retention_script.py`.
- [ ] Coordenador ciente de que `cannabia-audit-retention` comeca a rodar no proximo deploy.
- [ ] Issue/PR criada para acompanhamento do OK juridico antes do primeiro production purge.
- [ ] Calendar reminder (30d apos primeiro purge) para drop da snapshot table.
