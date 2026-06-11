# Sprint 3 — Track SCC-I1 (Integrity Hardening + Timestamp Standardization)

Aplicacao das migrations `022_integrity_hardening.sql` e
`023_timestamp_standardization.sql` em DB local + runbook operacional para
producao. Fecha a Frente I.I1 do `docs/22_EXECUTIVE_BACKLOG.md` como
pre-requisito do Sandbox Compliance Core (SCC).

## Status

- Branch: `feat/sprint-3-SCC-I1-integrity-timestamps`
- Phase 0 do coordenador respondida (Q-SCC-I1-1 a Q-SCC-I1-5).
- DB local Docker `cannabia-postgis:5434` UP (template `postgis/postgis:16-3.5-alpine`).
- Migrations 022 + 023 ja existem no repositorio desde 2026-04-19 (Sprint 1 D);
  Sprint 3 confirma aplicacao em dev, valida DOWN scripts e materializa o
  runbook operacional para producao.

## Decisoes do Coordenador

| Pergunta | Decisao |
|----------|---------|
| Q-SCC-I1-1 (apply prod) | TODO operacional. Sprint 3 dev so faz local + docs. Render.yaml ja auto-aplica via `preDeployCommand` no proximo deploy. |
| Q-SCC-I1-2 (DOWN dry-run) | DOWN scripts existem em `migrations/down/`; Sprint 3 testa UP->DOWN->UP em DB local separado. |
| Q-SCC-I1-3 (snapshot pre-prod) | `pg_dump` manual (comando exato abaixo). |
| Q-SCC-I1-4 (reconciliacao inter-env) | Rodar runner em todos os envs, detect via logs, INSERT manual em `schema_migrations` se preciso. |
| Q-SCC-I1-5 (escopo) | Local -> smoke -> docs. Staging/prod fora do escopo dev. |

## O Que Cada Migration Faz

### 022 — Integrity Hardening

Consolida 8 ajustes de integridade identificados na auditoria
`docs/progresso17_auditoria_completa_e_melhorias.md`, listados como
pre-requisitos obrigatorios antes da escrita de qualquer tabela do SCC.

**UP** (`migrations/022_integrity_hardening.sql`):

1. `CREATE UNIQUE INDEX uq_users_email_lower ON users (LOWER(email)) WHERE email IS NOT NULL AND email <> ''` — case-insensitive parcial.
2. `CREATE UNIQUE INDEX uq_triage_links_token_hash ON triage_links (token_hash)` + `DROP INDEX idx_triage_links_token_hash` (substitui o nao-unico criado pela 018).
3. `ALTER TABLE patients ADD CONSTRAINT fk_patients_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL` — pre-step zera orfaos.
4. `CHECK chk_patients_status` (whitelist: `ativo`, `inativo`, `em_tratamento`, `aguardando_consulta`, `arquivado`) — pre-step normaliza rows fora do whitelist para `ativo`.
5. `CHECK chk_treatment_plans_status` (whitelist + NULL permitido para planos pre-014) — normaliza para `ativo`.
6. `CHECK chk_anamnesis_reports_status` (whitelist: `pendente`, `revisado`, `arquivado`, `cancelado`) — normaliza para `pendente`.
7. `CREATE INDEX idx_ai_audit_logs_input_payload_gin USING GIN (input_payload)`.
8. `CREATE INDEX idx_ai_audit_logs_output_payload_gin USING GIN (output_payload) WHERE output_payload IS NOT NULL`.

Principios: idempotente (`IF NOT EXISTS`, `DO $$` checks em
`information_schema`), nao-destrutiva no DDL mas normaliza dados pre-existentes
para encaixar nos CHECKs antes de aplica-los.

**DOWN** (`migrations/down/022_integrity_hardening_down.sql`):

Reverte na ordem inversa (DROP INDEX GIN, DROP CHECK, DROP FK, DROP UNIQUE +
recria `idx_triage_links_token_hash` nao-unico, DROP `uq_users_email_lower`).

**Perda informacional documentada no proprio DOWN:** a normalizacao defensiva
da UP (orfaos zerados, status fora do whitelist convertidos para
`ativo`/`pendente`) **nao e revertivel** — os valores originais foram
descartados no momento da aplicacao. Recuperar exige restauracao por backup.

### 023 — Timestamp Standardization

Padroniza `TIMESTAMP` -> `TIMESTAMPTZ` nas colunas criadas pelas migrations
legadas `001_initial_schema.sql` e `003_anamnesis_reports.sql`. A ausencia de
fuso-horario produz inconsistencias em operacoes cross-table que usam `NOW()`
(TIMESTAMPTZ) e em ambientes com mais de uma zona de tempo (prod UTC vs dev
local).

**UP** (`migrations/023_timestamp_standardization.sql`):

1. `DROP VIEW IF EXISTS clinic_members` — pre-step, a view depende de `user_clinics.created_at` e impede o `ALTER COLUMN TYPE`.
2. Itera sobre 18 colunas TIMESTAMP em 14 tabelas; cada uma vira `TIMESTAMPTZ` via `ALTER TABLE %I ALTER COLUMN %I TYPE TIMESTAMPTZ USING %I AT TIME ZONE 'UTC'` (presume valores foram gravados em UTC).
3. Normaliza defaults para `NOW()` (sintaticamente compativel com `CURRENT_TIMESTAMP`, mas alinhado com as migrations 004+).
4. `CREATE OR REPLACE VIEW clinic_members` — identica a definicao da 014.

Tabelas/colunas no escopo (18):
`clinics.created_at`, `clinics.updated_at`, `patients.created_at`,
`ai_prompt_versions.created_at`, `users.created_at`, `user_clinics.created_at`,
`appointments.appointment_date`, `appointments.created_at`,
`message_status_updates.created_at`, `ai_audit_logs.created_at`,
`alerts.alert_time`, `alerts.created_at`, `medical_history.created_at`,
`monitoring.created_at`, `scientific_references.created_at`,
`treatment_plans.created_at`, `anamnesis_reports.created_at`,
`anamnesis_reports.updated_at`.

Principios: idempotente (verifica `information_schema.columns.data_type`
antes de converter; skip de tabelas/colunas ausentes em ambientes parciais).
Nao toca colunas ja TIMESTAMPTZ (definidas em 004+) nem
`incoming_messages.timestamp` (VARCHAR, fora de escopo).

**DOWN** (`migrations/down/023_timestamp_standardization_down.sql`):

Reverte 18 colunas TIMESTAMPTZ -> TIMESTAMP usando
`ALTER TABLE %I ALTER COLUMN %I TYPE TIMESTAMP USING %I AT TIME ZONE 'UTC'`,
preservando o wall-clock em UTC. Drop+recreate de `clinic_members` (mesmo
motivo da UP).

**Perda informacional documentada no proprio DOWN:** a conversao
TIMESTAMPTZ -> TIMESTAMP **descarta o fuso-horario**. O procedimento normaliza
todos os instantes para UTC antes de remover o tipo com fuso, preservando o
wall-clock mas removendo a informacao de origem. Se o banco ja tinha dados com
fusos locais misturados, essa perda e irreversivel via SQL.

## Comandos Executados em Dev (Local)

### Pre-requisito: DB local UP

```bash
docker start cannabia-postgis
# Verificar:
docker ps --filter "name=cannabia-postgis"
# cannabia-postgis    Up 34 seconds    0.0.0.0:5434->5432/tcp
docker exec cannabia-postgis pg_isready -U postgres
# /var/run/postgresql:5432 - accepting connections
```

### Apply via runner versionado (idempotente)

```bash
cd c:/Users/Administrador/Desktop/Cannabia
env/Scripts/python.exe -m src.infra.run_migrations
```

Output (com 022 + 023 ja aplicadas em 2026-04-19):

```
Nenhuma migration nova para aplicar.
```

Confirmar no `schema_migrations`:

```sql
SELECT version, filename, checksum FROM schema_migrations
 WHERE version IN ('022','023');
```

```
 version |             filename              |                             checksum
---------+-----------------------------------+----------------------------
 022     | 022_integrity_hardening.sql       | aaa3a2abfbd5a0582635df5189e5379ae1c20582d97dd92dbbd95a978a9b2cf0
 023     | 023_timestamp_standardization.sql | b9c977ca525555015251ca5c9e229cf431ab78a0e77f144fa6cb25d257cfed19
```

Checksums batem com o conteudo dos arquivos no HEAD — nenhuma alteracao
post-apply.

### Re-apply via psql para capturar RAISE NOTICE

Como o runner pula migrations ja registradas (checksum match), forcamos a
reaplicacao via `psql` direto para capturar a saida dos `DO $$ ... RAISE NOTICE`.

**022 re-apply (idempotente):**

```bash
cat migrations/022_integrity_hardening.sql \
  | docker exec -i cannabia-postgis psql -U postgres -d cannabia
```

```
CREATE INDEX
NOTICE:  relation "uq_users_email_lower" already exists, skipping
NOTICE:  relation "uq_triage_links_token_hash" already exists, skipping
CREATE INDEX
NOTICE:  index "idx_triage_links_token_hash" does not exist, skipping
DROP INDEX
DO        -- patients.user_id orfaos: 0 rows zeradas (estado limpo)
DO        -- patients.status normalizadas: 0 rows alteradas (whitelist OK)
DO        -- treatment_plans.status normalizadas: 0 rows alteradas
DO        -- anamnesis_reports.status normalizadas: 0 rows alteradas
NOTICE:  relation "idx_ai_audit_logs_input_payload_gin" already exists, skipping
NOTICE:  relation "idx_ai_audit_logs_output_payload_gin" already exists, skipping
CREATE INDEX
```

**023 re-apply (idempotente):**

```bash
cat migrations/023_timestamp_standardization.sql \
  | docker exec -i cannabia-postgis psql -U postgres -d cannabia
```

```
DROP VIEW
NOTICE:  ok (ja tztz): clinics.created_at
NOTICE:  ok (ja tztz): clinics.updated_at
NOTICE:  ok (ja tztz): patients.created_at
NOTICE:  ok (ja tztz): ai_prompt_versions.created_at
NOTICE:  ok (ja tztz): users.created_at
NOTICE:  ok (ja tztz): user_clinics.created_at
NOTICE:  ok (ja tztz): appointments.appointment_date
NOTICE:  ok (ja tztz): appointments.created_at
NOTICE:  ok (ja tztz): message_status_updates.created_at
NOTICE:  ok (ja tztz): ai_audit_logs.created_at
NOTICE:  ok (ja tztz): alerts.alert_time
NOTICE:  ok (ja tztz): alerts.created_at
NOTICE:  ok (ja tztz): medical_history.created_at
NOTICE:  ok (ja tztz): monitoring.created_at
NOTICE:  ok (ja tztz): scientific_references.created_at
NOTICE:  ok (ja tztz): treatment_plans.created_at
NOTICE:  ok (ja tztz): anamnesis_reports.created_at
NOTICE:  ok (ja tztz): anamnesis_reports.updated_at
DO
DO
CREATE VIEW
```

**Contagem de rows normalizadas pela 022 em dev local: 0 em todas as colunas.**
O ambiente esta limpo — todos os `user_id` apontam para `users` existentes,
todos os `status` estao no whitelist. Em prod a contagem pode ser >0 caso
existam orfaos historicos; o `DO $$` block silenciosamente normaliza antes do
CHECK.

## Schema Diff (Antes/Depois)

Capturado via `\d+` apos aplicacao.

### `\d+ users` (apos 022+023)

```
 id              | integer                  | not null | nextval(...)
 username        | varchar(50)              | not null
 password_hash   | varchar(255)             | not null
 role            | varchar(20)              | not null | 'Medico'
 is_active       | boolean                  |          | true
 created_at      | timestamp with time zone | not null | now()      <-- 023
 email           | varchar(255)
 full_name       | varchar(255)
 updated_at      | timestamp with time zone |          | now()      <-- 023
 is_clinic_admin | boolean                  | not null | false
Indexes:
    "users_pkey" PRIMARY KEY, btree (id)
    "idx_users_email" btree (email)
    "idx_users_role" btree (role)
    "uq_users_email_lower" UNIQUE, btree (lower(email::text))
                 WHERE email IS NOT NULL AND email::text <> ''::text   <-- 022
    "users_username_key" UNIQUE CONSTRAINT, btree (username)
```

### `\d+ patients` (apos 022+023)

```
 id         | integer                  | not null | nextval(...)
 clinic_id  | integer                  | not null | 1
 name       | varchar(100)             | not null
 email      | varchar(100)
 phone      | varchar(20)
 created_at | timestamp with time zone | not null | now()        <-- 023
 user_id    | integer
 status     | varchar(50)              |          | 'ativo'
Indexes:
    "patients_pkey" PRIMARY KEY, btree (id)
    "idx_patients_clinic_id" btree (clinic_id)
    "idx_patients_user_id" btree (user_id)
Check constraints:
    "chk_patients_status" CHECK (status IN
        ('ativo','inativo','em_tratamento','aguardando_consulta','arquivado')) <-- 022
Foreign-key constraints:
    "fk_patients_clinic" FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE RESTRICT
    "fk_patients_user"   FOREIGN KEY (user_id)   REFERENCES users(id)   ON DELETE SET NULL <-- 022
```

### `\d+ clinic_members` (view recriada pela 023)

```
View definition:
 SELECT user_id, clinic_id, role AS clinic_role, is_default, created_at
   FROM user_clinics;
```

`created_at` herda o tipo de `user_clinics.created_at` — agora `TIMESTAMPTZ`.

## Smoke Tests Pos-Apply

```bash
env/Scripts/python.exe -m pytest --no-cov -q \
  tests/test_migrations_integrity_hardening.py \
  tests/test_clinical_flow.py \
  tests/test_database_pool.py
```

```
collected 44 items

tests\test_migrations_integrity_hardening.py ........................... [ 61%]
.......                                                                  [ 77%]
tests\test_clinical_flow.py .......                                      [ 93%]
tests\test_database_pool.py ...                                          [100%]

============================= 44 passed in 24.90s =============================
```

Breakdown:
- `test_migrations_integrity_hardening.py`: **34 testes** (o backlog declarava 30 — atualizar contagem).
- `test_clinical_flow.py`: 7 testes (smoke pipeline anamnese → plano).
- `test_database_pool.py`: 3 testes (smoke conexao psycopg2 + connection pool).

## DOWN Scripts Dry-Run (UP→DOWN→UP)

Executado em DB transient `cannabia_dryrun` criado a partir do template
`cannabia` (preserva o DB live intacto).

### Setup

```bash
docker exec cannabia-postgis psql -U postgres \
  -c "DROP DATABASE IF EXISTS cannabia_dryrun;"
docker exec cannabia-postgis psql -U postgres \
  -c "CREATE DATABASE cannabia_dryrun TEMPLATE cannabia;"
```

### Apply DOWN 023 → DOWN 022

```bash
cat migrations/down/023_timestamp_standardization_down.sql \
  | docker exec -i cannabia-postgis psql -U postgres -d cannabia_dryrun
```

Output (extrato):

```
DROP VIEW
NOTICE:  reverted: clinics.created_at -> TIMESTAMP (UTC wall-clock)
NOTICE:  reverted: clinics.updated_at -> TIMESTAMP (UTC wall-clock)
NOTICE:  reverted: patients.created_at -> TIMESTAMP (UTC wall-clock)
... (18 colunas)
NOTICE:  reverted: anamnesis_reports.updated_at -> TIMESTAMP (UTC wall-clock)
CREATE VIEW
```

```bash
cat migrations/down/022_integrity_hardening_down.sql \
  | docker exec -i cannabia-postgis psql -U postgres -d cannabia_dryrun
```

```
DROP INDEX     -- GIN input_payload
DROP INDEX     -- GIN output_payload
ALTER TABLE    -- DROP CHECK chk_anamnesis_reports_status
ALTER TABLE    -- DROP CHECK chk_treatment_plans_status
ALTER TABLE    -- DROP CHECK chk_patients_status
ALTER TABLE    -- DROP CONSTRAINT fk_patients_user
DROP INDEX     -- uq_triage_links_token_hash
CREATE INDEX   -- idx_triage_links_token_hash (nao-unico, restaurado)
DROP INDEX     -- uq_users_email_lower
```

Verificacao:

```sql
SELECT data_type FROM information_schema.columns
 WHERE table_name='users' AND column_name='created_at';
-- timestamp without time zone

SELECT data_type FROM information_schema.columns
 WHERE table_name='patients' AND column_name='created_at';
-- timestamp without time zone

SELECT COUNT(*) FROM information_schema.table_constraints
 WHERE constraint_name='chk_patients_status';
-- 0 (removida)

SELECT COUNT(*) FROM information_schema.table_constraints
 WHERE constraint_name='fk_patients_user';
-- 0 (removida)

SELECT indexname FROM pg_indexes
 WHERE indexname IN
   ('uq_users_email_lower','uq_triage_links_token_hash',
    'idx_triage_links_token_hash','idx_ai_audit_logs_input_payload_gin');
-- idx_triage_links_token_hash (somente o nao-unico recriado)
```

### Re-apply UP 022 → UP 023

```bash
cat migrations/022_integrity_hardening.sql \
  | docker exec -i cannabia-postgis psql -U postgres -d cannabia_dryrun
cat migrations/023_timestamp_standardization.sql \
  | docker exec -i cannabia-postgis psql -U postgres -d cannabia_dryrun
```

Verificacao final:

```sql
SELECT data_type FROM information_schema.columns
 WHERE table_name='users' AND column_name='created_at';
-- timestamp with time zone

SELECT COUNT(*) FROM information_schema.table_constraints
 WHERE constraint_name='chk_patients_status';
-- 1 (recriada)

SELECT COUNT(*) FROM information_schema.table_constraints
 WHERE constraint_name='fk_patients_user';
-- 1 (recriada)
```

### Cleanup

```bash
docker exec cannabia-postgis psql -U postgres \
  -c "DROP DATABASE cannabia_dryrun;"
```

**Conclusao do dry-run:** ciclo UP -> DOWN -> UP completo em DB transient,
todos os artifacts revertidos e recriados conforme esperado. Idempotencia
confirmada nos dois sentidos.

**Reforco da honestidade documentada nos proprios scripts:**
- A perda informacional da UP 022 (rows normalizadas para encaixar nos CHECKs;
  user_ids orfaos zerados) **nao e revertivel** via DOWN. Em prod com dados
  reais, isso seria irreversivel sem restore por backup.
- A perda informacional da DOWN 023 (TIMESTAMPTZ -> TIMESTAMP descarta fuso) e
  irreversivel via SQL caso o DB tenha tido dados com fusos locais misturados.
  No nosso caso (servidor Render UTC, defaults `CURRENT_TIMESTAMP` em conexao
  UTC), a perda e zero pratica — mas a documentacao do DOWN preserva a
  honestidade.

## Plano de Backup Pre-Prod

Antes de aplicar 022+023 em producao, **executar pg_dump manual** (decisao
Q-SCC-I1-3):

```bash
# 1. Capturar DATABASE_URL do Render dashboard
export DATABASE_URL="postgresql://cannabia_user:...@dpg-...oregon-postgres.render.com/cannabia"

# 2. Dump compactado (format custom)
pg_dump "$DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-acl \
  --file=cannabia_pre_scc_I1_$(date +%Y%m%d).dump

# 3. Validar o dump (lista de objetos, nao restaura nada)
pg_restore --list cannabia_pre_scc_I1_$(date +%Y%m%d).dump | head -20

# 4. Armazenar em local seguro (S3 / equivalente) com checksum
sha256sum cannabia_pre_scc_I1_$(date +%Y%m%d).dump \
  > cannabia_pre_scc_I1_$(date +%Y%m%d).dump.sha256
```

Tamanho esperado: ordem de dezenas de MB (estimativa baseada no schema atual +
seed). Conservar o dump por, no minimo, 90 dias (compativel com retencao LGPD
da Sprint 2 LGPD-Purge).

## Plano de Rollback (Producao)

Caso a aplicacao em prod cause regressao detectada por smoke pos-deploy,
executar nesta ordem:

```bash
# 1. Captura DATABASE_URL
export DATABASE_URL="postgresql://..."

# 2. DOWN 023 PRIMEIRO (depende da view clinic_members existir, recriada pela UP 023)
psql "$DATABASE_URL" -f migrations/down/023_timestamp_standardization_down.sql

# 3. DOWN 022
psql "$DATABASE_URL" -f migrations/down/022_integrity_hardening_down.sql

# 4. Remover registro do schema_migrations (manual, conforme nota dos DOWN scripts)
psql "$DATABASE_URL" -c "DELETE FROM schema_migrations WHERE version IN ('022','023');"
```

**Importante:** o `preDeployCommand` do Render re-executa o runner no proximo
deploy, que tentara re-aplicar 022+023. Para evitar, ha 3 opcoes:

1. **Revert do PR** (preferido): `git revert` do merge → push → novo deploy
   sem os arquivos da Sprint 3 SCC-I1 (mas os arquivos das migrations sao do
   Sprint 1 D — soh o doc novo seria revertido). Esta opcao **nao** previne
   re-apply.
2. **Hotfix temporario**: comentar `preDeployCommand` no `render.yaml`,
   deploy, restaurar do backup, descomentar.
3. **Restore do dump**: a opcao mais segura se os DOWN scripts nao
   conseguirem reverter (ex: dados ja regravados com a nova restricao).

### AVISO — Auto-Apply em Producao

`render.yaml:12`:

```yaml
preDeployCommand: python -m src.infra.run_migrations
```

**Toda push para `main` que dispara deploy aplica migrations pendentes
AUTOMATICAMENTE em producao.** No proximo deploy posterior ao merge deste PR,
as migrations 022 e 023 (e qualquer outra ainda pendente em prod) serao
aplicadas sem confirmacao manual.

**Mitigacao operacional (coordenador):**

1. Antes de fazer merge para `main`, fazer `pg_dump` (comando acima).
2. Agendar janela de baixa atividade.
3. Fazer merge, monitorar o deploy log do Render (procurar pelas linhas
   `Aplicando migration 022 (022_integrity_hardening.sql)...` e
   `Aplicando migration 023 (023_timestamp_standardization.sql)...`).
4. Executar smoke `pytest tests/test_migrations_integrity_hardening.py`
   contra prod (via tunel) ou inspecionar `\d+ users`, `\d+ patients` direto
   em prod via Render shell.
5. Se falhar: rollback via DOWN scripts (acima).

## Reconciliacao Inter-Env (Q-SCC-I1-4)

Apos o deploy de prod aplicar as migrations, rodar o runner em qualquer
ambiente staging/dev pode falhar com **checksum mismatch** se algum arquivo
foi editado entre aplicacoes. Procedimento:

1. Comparar a coluna `checksum` do `schema_migrations` entre envs:
   ```sql
   SELECT version, checksum FROM schema_migrations
    WHERE version IN ('022','023');
   ```
2. Se houver mismatch, recalcular o SHA-256 do arquivo no HEAD:
   ```bash
   python -c "import hashlib; print(hashlib.sha256(open('migrations/022_integrity_hardening.sql','rb').read()).hexdigest())"
   ```
3. INSERT manual em `schema_migrations` no env atrasado caso a migration ja
   tenha sido aplicada por outra via (psql direto):
   ```sql
   INSERT INTO schema_migrations (version, filename, checksum)
   VALUES ('022', '022_integrity_hardening.sql', '<sha>')
   ON CONFLICT (version) DO UPDATE
     SET filename = EXCLUDED.filename, checksum = EXCLUDED.checksum;
   ```

## Arquivos Tocados pela Sprint 3 SCC-I1

- `docs/sprints/sprint_3_SCC_I1.md` — este arquivo (runbook + plano).
- `docs/22_EXECUTIVE_BACKLOG.md` — atualiza linha 177 (I1) com status
  `aplicado em dev/local`, contagem corrigida (30 -> 34 testes), explicita
  auto-apply via `render.yaml:12` e production = TODO operacional.

**Nao toca em:**

- `migrations/022_integrity_hardening.sql` — ja existe (Sprint 1 D).
- `migrations/023_timestamp_standardization.sql` — ja existe (Sprint 1 D).
- `migrations/down/022_integrity_hardening_down.sql` — ja existe.
- `migrations/down/023_timestamp_standardization_down.sql` — ja existe.
- `tests/test_migrations_integrity_hardening.py` — ja existe com 34 testes.

## TODO Operacional (Coordenador)

- [ ] `pg_dump` do DB prod conforme comando acima e armazenar com sha256.
- [ ] Agendar janela de deploy de baixa atividade.
- [ ] Merge do PR `feat/sprint-3-SCC-I1-integrity-timestamps`.
- [ ] Acompanhar o deploy log do Render durante o `preDeployCommand`.
- [ ] Smoke pos-apply em prod: validar `\d+ users` e `\d+ patients`.
- [ ] Em caso de regressao, executar plano de rollback (DOWN scripts ou
      restore do dump).
