# Progresso 18 — Integrity Hardening + Timestamp Standardization

## Data

2026-04-19

## Objetivo do bloco

Fechar a **Fase 0** do `docs/BACKLOG_SCC.md` — sanear a base antes de qualquer escrita do Sandbox Compliance Core em tabelas append-only:

1. Escrever a migration `022_integrity_hardening.sql` cobrindo os achados de Prioridade 1 do `progresso17_auditoria_completa_e_melhorias.md` (UNIQUE, FK, CHECK, GIN).
2. Escrever a migration `023_timestamp_standardization.sql` convertendo as colunas `TIMESTAMP` legadas das migrations `001` e `003` para `TIMESTAMPTZ`.
3. Garantir cobertura de testes estatica para ambas, usando o padrao adotado em `tests/test_migrations.py` (sem dependencia de banco real).

## Trabalho realizado

### 1. Migration 022 — Integrity Hardening

Arquivo: `migrations/022_integrity_hardening.sql`

Oito ajustes de integridade em uma unica migration idempotente:

- **UNIQUE case-insensitive** em `users.email` via `uq_users_email_lower` (partial index, ignora NULL/vazio).
- **UNIQUE** em `triage_links.token_hash` via `uq_triage_links_token_hash`, removendo o indice nao-unico `idx_triage_links_token_hash` introduzido em 018.
- **FK** `patients.user_id → users(id)` com `ON DELETE SET NULL`, precedida por uma normalizacao que zera `user_id`s orfaos para evitar quebra em ambientes com dados historicos.
- **CHECK** em `patients.status` com whitelist `(ativo, inativo, em_tratamento, aguardando_consulta, arquivado)`. Normaliza rows com status NULL ou fora do whitelist para `ativo` antes de aplicar o CHECK.
- **CHECK** em `treatment_plans.status` com whitelist `(ativo, inativo, suspenso, concluido, arquivado)`, **permitindo NULL** (rows pre-014 podem ter a coluna nula). Normaliza apenas rows com status nao-NULL fora do whitelist.
- **CHECK** em `anamnesis_reports.status` com whitelist `(pendente, revisado, arquivado, cancelado)`. Normaliza rows fora do whitelist para `pendente`.
- **GIN index** em `ai_audit_logs.input_payload` via `idx_ai_audit_logs_input_payload_gin`.
- **GIN index** parcial em `ai_audit_logs.output_payload` via `idx_ai_audit_logs_output_payload_gin` com `WHERE output_payload IS NOT NULL`.

Todos os DDLs condicionais ficam dentro de blocos `DO $$` que consultam `information_schema` antes de alterar o schema, permitindo reexecucao sem efeito colateral. Todos os `CREATE INDEX`/`CREATE UNIQUE INDEX` usam `IF NOT EXISTS`. Nenhum `INSERT INTO schema_migrations` embutido (o runner versionado cuida do tracking desde `progresso10`).

### 2. Migration 023 — Timestamp Standardization

Arquivo: `migrations/023_timestamp_standardization.sql`

Converte todas as colunas `TIMESTAMP` sem fuso-horario criadas em `001_initial_schema.sql` e `003_anamnesis_reports.sql` para `TIMESTAMPTZ`, assumindo origem UTC:

- 18 pares (tabela, coluna) processados em loop unico via `FOR` sobre um array `TEXT[][]`, incluindo:
  - `clinics.{created_at, updated_at}`
  - `patients.created_at`
  - `ai_prompt_versions.created_at`
  - `users.created_at`
  - `user_clinics.created_at`
  - `appointments.{appointment_date, created_at}`
  - `message_status_updates.created_at`
  - `ai_audit_logs.created_at`
  - `alerts.{alert_time, created_at}`
  - `medical_history.created_at`
  - `monitoring.created_at`
  - `scientific_references.created_at`
  - `treatment_plans.created_at`
  - `anamnesis_reports.{created_at, updated_at}`

- Cada conversao usa:
  - `ALTER COLUMN ... TYPE TIMESTAMPTZ USING <coluna> AT TIME ZONE 'UTC'` — preserva o instante exato ao atribuir fuso explicito.
  - Guard em `information_schema.columns.data_type` para pular colunas ja convertidas ou ausentes em ambientes parciais.
  - `RAISE NOTICE` para observabilidade do conversor.

- Segundo bloco `DO $$` padroniza `DEFAULT NOW()` nas colunas convertidas, alinhando com as migrations mais recentes (020, 021) que ja usam esse padrao.

Idempotente: reexecucao detecta o tipo atual como `timestamp with time zone` e pula a conversao.

**Fora do escopo desta migration (propositalmente):**

- `incoming_messages.timestamp` e `message_status_updates.timestamp` sao `VARCHAR(50)`. Normalizar para `TIMESTAMPTZ` exige migracao de dados nao-triviaI (parse de strings de origem Meta) e fica para ciclo posterior.
- Colunas TIMESTAMPTZ ja corretas (004+) nao sao alteradas.

### 3. Cobertura de testes

Arquivo: `tests/test_migrations_integrity_hardening.py`

30 testes estaticos cobrindo ambas as migrations:

- **Estrutura geral** — cabecalho, ausencia de INSERT manual em `schema_migrations`, uso de `AT TIME ZONE 'UTC'`.
- **DDL especifico** — cada constraint/indice/conversao mencionada tem um teste dedicado validando o nome canonico esperado e os atributos criticos (por exemplo, `ON DELETE SET NULL` na FK, `WHERE email IS NOT NULL` no indice unico parcial, `IF NOT EXISTS` em todos os `CREATE INDEX`).
- **Whitelists de status** — todo valor observado no `scripts/seed_comprehensive.py` esta presente no CHECK, garantindo que a migration nao quebra dados de seed reais.
- **Idempotencia** — DO $$ blocos com verificacoes em `information_schema`, IF NOT EXISTS em todos os indices, existence guards antes de ALTER COLUMN.
- **Sanity cross-migration** — nenhum identificador do SCC (tabelas tipo `association_members`, `traceability_events` etc.) aparece prematuramente nas 022/023.

Os testes sao **static analysis** dos arquivos SQL (nao requerem Postgres), alinhados ao padrao de `tests/test_migrations.py`, que tambem nao depende de banco real. Validacao dinamica contra um Postgres real fica para `scripts/setup_local.py`.

## Validacoes executadas

Dentro do sandbox Linux desta sessao (sem psycopg2 instalado, conforme esperado):

```
python3 -m pip install pytest --break-system-packages
python3 -m pytest tests/test_migrations_integrity_hardening.py -v
```

Resultado: **30 passed in 0.90s**. A suite isolada da 022/023 passa integral porque nao depende de `src.infra.database` (que exige psycopg2).

Em ambiente local completo (com `env\Scripts\python.exe` + psycopg2 + Postgres apontado por `DATABASE_URL`), a validacao recomendada para a proxima sessao e:

```
env\Scripts\python.exe -m pytest -q
env\Scripts\python.exe scripts/setup_local.py
psql $DATABASE_URL -c "SELECT version, filename FROM schema_migrations ORDER BY version"
```

A saida esperada do segundo comando inclui registros `022` e `023` com checksum preenchido.

## Decisoes registradas

1. **Normalizacao defensiva antes de CHECK** — em vez de usar `ALTER TABLE ... ADD CONSTRAINT ... NOT VALID`, optamos por normalizar os valores pre-existentes para o whitelist antes de adicionar o CHECK. Isso elimina a fragilidade operacional de ter constraints nao validadas em producao e explicita os invariantes desde a aplicacao da migration.

2. **Whitelists permissivas, com `arquivado` reservado** — todos os CHECKs incluem `arquivado` como estado de ciclo de vida final, mesmo sem uso atual no codigo, para evitar uma 024/025 so para aceitar esse valor quando o SCC comecar a arquivar rows.

3. **TIMESTAMPTZ por loop declarativo** — em vez de repetir 18 `ALTER TABLE`, o script itera sobre um array `TEXT[][]` de pares (tabela, coluna), o que torna o padrao auditavel de relance e reutilizavel caso outras migrations precisem de conversoes semelhantes.

4. **`incoming_messages.timestamp` fica fora da 023** — e uma coluna `VARCHAR` com formato proprio da Meta. Normalizar exige parse de string e migracao de dados, tratado como dividendo separado, nao parte da padronizacao de fuso.

5. **Nao alteramos arquivos tocados na sessao anterior** — dado que os commits das docs 23-27 ainda nao foram feitos, trabalhamos exclusivamente em arquivos novos (migrations novas + teste novo) para evitar misturar a Fase 0 com a serie SCC na arvore de staging.

## Observacao de documentacao cruzada

O comentario em `src/services/telemetry_crm_service.py:90` menciona valores em ingles (`'pending'`, `'reviewed'`) que **nao** correspondem ao whitelist real (`pendente`, `revisado`). E uma docstring, nao afeta a SQL — foi deliberadamente deixada como esta para nao atravessar sessoes de commit. Fica registrada como follow-up de limpeza.

## Estado apos o bloco

### Fechado

- Os 8 ajustes de integridade da Prioridade 1 (`progresso17`).
- Padronizacao `TIMESTAMPTZ` para `001` e `003`.
- 30 testes estaticos cobrindo as duas migrations.
- Pre-requisitos P0.1 e P0.2 do `docs/BACKLOG_SCC.md` concluidos.

### Ainda aberto (Fase 0)

- P0.3 — CI minimo (`.github/workflows/ci.yml`) rodando `pytest -q` + `tsc --noEmit` em PRs.
- P0.4 — `.env.example` completo (`DEFAULT_CLINIC_ID`, `TELEMETRY_*`, `PAYMENT_WEBHOOK_SECRET_*`).
- P0.5 — politica formal de backup/DR + scripts `migrations/down/` para rollback.
- Commit pendente das docs 23-27 gerados no bloco anterior (`HANDOFF_VALIDATION_REPORT.md` documenta a integracao).

### Sugestao para a proxima sessao

1. Rodar `env\Scripts\python.exe scripts/setup_local.py` para aplicar 022/023 em Postgres local e inspecionar visualmente o estado final do schema.
2. Fechar P0.3 — CI em GitHub Actions com `pytest` + `tsc --noEmit`.
3. Fechar P0.4 — `.env.example` com todas as chaves faltantes.
4. Abrir Fase 1 do SCC — migration `024_tenants_evolution.sql` com evolucao `clinics → tenants` tipados.

## Arquivos relevantes do bloco

### Criados

- `migrations/022_integrity_hardening.sql`
- `migrations/023_timestamp_standardization.sql`
- `tests/test_migrations_integrity_hardening.py`
- `docs/progresso18_integrity_hardening.md`

### Modificados

- Nenhum. O bloco foi executado exclusivamente via adicao, preservando a arvore de staging da sessao anterior (serie SCC 23-27) para commit em bloco separado.

## Primeira missao sugerida para a proxima sessao

Aplicar `022_integrity_hardening.sql` e `023_timestamp_standardization.sql` em ambiente local via `scripts/setup_local.py`, validar por `SELECT data_type FROM information_schema.columns WHERE ...` que as colunas estao como `timestamp with time zone`, e confirmar por `\d patients`, `\d treatment_plans`, `\d anamnesis_reports` que os CHECK constraints estao presentes. Se tudo verde, abrir P0.3 (CI).
