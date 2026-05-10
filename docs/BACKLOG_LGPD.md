# Backlog LGPD — Dívidas técnicas registradas

> **Origem:** Sprint 1 Track A (Security + LGPD critical). Criado em 2026-05-10 quando A.3 (PII redaction estrutural em `ai_audit_logs`) foi implementado.

## Princípio: A.3 sanitiza só forward

`sanitize_clinical_payload` em [src/ai/audit_redaction.py](../src/ai/audit_redaction.py) é aplicado em [src/repositories/ai_audit_repository.py:67-68](../src/repositories/ai_audit_repository.py) antes do `json.dumps`. Cobre **toda gravação a partir do merge de A.3**. Logs gravados ANTES disso passaram in claro.

**Fora do escopo de A.3:** purge retroativo. Risco operacional de varrer logs em produção sem janela definida + sem schema de evento de purge auditável. Vai pra Sprint 2.

## Dívida 1 — Purge retroativo de logs PII em `ai_audit_logs`

**Sprint:** 2 (a definir).

### Diagnóstico inicial

Query de count pra dimensionar volume antes de planejar purge:

```sql
-- Logs anteriores ao merge de A.3 (ajustar timestamp ao merge)
SELECT COUNT(*) AS total,
       MIN(created_at) AS oldest,
       MAX(created_at) AS newest
FROM ai_audit_logs
WHERE created_at < '2026-05-10 14:00:00';

-- Spot-check: registros com CPF em texto plano nos JSONB
SELECT id, request_id, created_at
FROM ai_audit_logs
WHERE input_payload::text ~ '\d{3}\.\d{3}\.\d{3}-\d{2}'
   OR output_payload::text ~ '\d{3}\.\d{3}\.\d{3}-\d{2}'
LIMIT 20;

-- Idem com email
SELECT id, request_id, created_at
FROM ai_audit_logs
WHERE input_payload::text ~ '[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+'
LIMIT 20;
```

### Opções de tratamento

1. **Re-sanitização in-place:** UPDATE em batch aplicando `sanitize_clinical_payload` a `input_payload` e `output_payload`. Preserva auditoria dos campos clínicos não-sensíveis. Risco: bug no sanitizer corrompe registros — exigir snapshot antes.
2. **DELETE seletivo:** apagar registros com PII detectado (regex check via SQL). Perde auditoria histórica.
3. **Anonymização agressiva:** trocar payload inteiro por `{"_purged": true, "_purged_at": ...}`. Perde tudo exceto metadata (`request_id`, `endpoint`, `tokens`, `cost`, `created_at`).

**Recomendação:** opção 1 com snapshot em `ai_audit_logs_pre_redact_backup` (DROP TABLE ao final da Sprint 2 após validação).

## Dívida 2 — Retention policy

**Sprint:** 2.

LGPD exige justificativa de retenção e prazos de descarte. Hoje não há retention policy em `ai_audit_logs`. Definir:

- Prazo padrão (ex: 5 anos pós último acesso? ou pós inatividade do paciente?).
- Trigger de DELETE automático (cron diária / pgAgent / GitHub Actions schedule).
- Eventos de purge gravados em `audit_trail` (criado em [migrations/008_audit_trail.sql](../migrations/008_audit_trail.sql)) pra rastreabilidade.

## Dívida 3 — Rotação de SECRET_KEY exige re-encryption

**Sprint:** 2 ou 3 (planejar).

[src/infra/crypto.py](../src/infra/crypto.py) deriva chave Fernet **ao import** ([linha 70-71](../src/infra/crypto.py)). Se SECRET_KEY for rotacionado em produção, dados criptografados com a chave antiga ficam ilegíveis (R3 da Phase 0 do Track A).

A.4 mitigou parcialmente: render.yaml já gera `ENCRYPTION_KEY` separada (linha 47), e crypto.py raise em prod sem ela ([crypto.py:51-58](../src/infra/crypto.py)). Mas:

- Não há mecanismo de re-encryption se ENCRYPTION_KEY rotacionar.
- Não há verificação de qual chave foi usada pra cada ciphertext (sem header de versão).

**Plano sugerido:**

1. Adicionar `ENCRYPTION_KEY_VERSION` ao schema (coluna numérica em tabelas com `_encrypted` columns).
2. Implementar `encrypt_value(plaintext, version=current)` + `decrypt_value(ciphertext, version=row.version)`.
3. Migration de re-encryption usando dual-key window (decrypta com v1, encripta com v2, atualiza version).

## Dívida 4 — Auditoria de gravações pré-A.3 em `medical_record_entries` e `anamnesis_reports`

**Sprint:** 2.

PII também flui para [migrations/003_anamnesis_reports.sql](../migrations/003_anamnesis_reports.sql) (`anamnesis_data`, `clinical_analysis`, `treatment_plan`, `scientific_report` JSONB) e [migrations/006_medical_records_foundation.sql](../migrations/006_medical_records_foundation.sql) (`medical_observations`, `clinical_assessment`, `conduct`, `follow_up_plan` TEXT).

A.3 cobre só `ai_audit_logs`. As outras tabelas têm justificativa clínica para guardar PII (são prontuário oficial, não logs operacionais), mas:

- Acesso deve ser auditado em `audit_trail`.
- Campos sensíveis dentro de JSONB (CPF/RG embutidos em texto livre) são candidatos a sanitização ou criptografia at-rest.

## Dívida 5 — Defensiva crypto: warning vs raise em dev

**Sprint:** baixa prioridade.

[crypto.py:55-58](../src/infra/crypto.py) loga warning quando `ENCRYPTION_KEY` ausente em dev (deriva Fernet de SECRET_KEY). Aceitável, mas devs novos podem ignorar warning. Considerar:

- Warning louder (logger.error em vez de warning?).
- Adicionar check no `tests/conftest.py` que falha se `ENCRYPTION_KEY` não for setada e `FLASK_ENV != "test"`.
- Documentar em README.md de setup.
