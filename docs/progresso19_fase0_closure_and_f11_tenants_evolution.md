# Progresso 19 — Fase 0 Closure + F1.1 (Tenants Evolution)

## Data

2026-04-19 (sessão noturna; continua o dia do `progresso18_integrity_hardening.md`)

## Objetivo do bloco

Após a sessão do Cowork ter entregue a série SCC 23-27 + as migrations 022/023 + o bloco de integrity hardening (progresso18), encerrar a **Fase 0** do `docs/BACKLOG_SCC.md` e abrir a **Fase 1** com a migration fundacional de tenants evoluídos.

Especificamente:

1. Aplicar 022 e 023 em Postgres local e validar o schema resultante.
2. Fechar P0.3 (CI GitHub Actions), P0.4 (`.env.example` completo) e P0.5 (política de backup/DR + `migrations/down/` para rollback).
3. Commitar em grupos semânticos todo o trabalho que estava uncommitted (cowork + desta sessão).
4. Abrir F1.1 — migration `024_tenants_evolution.sql` — evolução da tabela `tenants` com os campos do doc 25 §4.1.

## Trabalho realizado

### 1. Limpeza inicial do repositório

Com autorização explícita do usuário, removidos do root: caches (`pytest-cache-files-*`, `tmpk*`, `.pytest_tmp`, `__pycache__`), logs antigos (`cannabia.log` 724KB, `backend_flask.*`, `frontend_dev*`, `cookies.txt`), scripts bootstrap obsoletos (`check_db.py`, `create_admin.py`, `fix_admin.py`, `auditoriasistema1.md`), anexos soltos (imagens, PDFs e DOCX de rascunho) e os zips em `referencias_ux/`. Preservados: `HANDOFF_VALIDATION_REPORT.md`, `docs/` completo incluindo todos os progressos 1-18, `imagens/`, `Brigaf News #1.pdf`, pasta `stitch_cannab_ia_ui_refactor/` extraída.

### 2. Aplicação das migrations 022 e 023 (P0.1 + P0.2)

Rodado `scripts/setup_local.py` apontado para `$DATABASE_URL`. Primeira tentativa falhou na 023:

```
ERRO: nao e possivel alterar o tipo de dados de uma coluna usada por uma visao
DETAIL: regra _RETURN em visao clinic_members depende da coluna "created_at"
CONTEXT: ALTER TABLE user_clinics ALTER COLUMN created_at TYPE TIMESTAMPTZ ...
```

A view `clinic_members` (criada em `014_missing_tables_and_columns.sql`) referencia `user_clinics.created_at` e bloqueia o `ALTER COLUMN TYPE`. Descoberto apenas ao aplicar em Postgres real — a cobertura estática de `tests/test_migrations_integrity_hardening.py` não alcançava esse caso.

**Correção aplicada**: adicionado `DROP VIEW IF EXISTS clinic_members;` no início de `migrations/023_timestamp_standardization.sql`, antes do loop de `ALTER COLUMN`, e `CREATE OR REPLACE VIEW clinic_members AS ...` no final para recriar a view com a definição idêntica a 014. Mais 4 testes estáticos adicionados em `TestMigration023ViewHandling` validando a existência do drop+recreate e sua ordem correta em relação ao loop.

Após o fix, re-execução aplicou 022 + 023 e validou por `psql`:

- `schema_migrations` com 022 e 023 registrados e com checksum correto.
- 4 constraints presentes: `chk_patients_status`, `chk_treatment_plans_status`, `chk_anamnesis_reports_status`, `fk_patients_user` (ON DELETE SET NULL).
- 4 indexes novos: `uq_users_email_lower` (partial + lower), `uq_triage_links_token_hash`, `idx_ai_audit_logs_input_payload_gin`, `idx_ai_audit_logs_output_payload_gin` (partial).
- Índice legado `idx_triage_links_token_hash` removido.
- 20 colunas `TIMESTAMP` convertidas para `TIMESTAMPTZ`.
- View `clinic_members` recriada.

### 3. Série SCC e Fase 0 commitadas em 7 grupos semânticos

Até aqui o repositório tinha 104 arquivos uncommitted (mistura de sessão do Cowork, trabalho das Sprints 6-8 nunca commitado, e este bloco). Para manter histórico legível, commitei somente o escopo da sessão do Cowork e desta sessão em grupos semânticos:

1. `81e4c01` docs(scc): série Sandbox Compliance Core (23-27) + backlog + handoff.
2. `16cc3e1` docs(cross-refs): alinha docs canônicos com a série SCC.
3. `83357a1` migrations(022-023): integrity hardening + timestamp standardization.
4. `69f1a69` tests(migrations): cobertura estática de 022/023 (34 testes).
5. `c048be0` docs(progresso18): bloco de integrity hardening.
6. `313ccbd` ci(p0.3): GitHub Actions rodando pytest + tsc em PRs e pushes.
7. `4fc3ce2` docs(env): completa `.env.example` com todas as chaves lidas pelo código.

### 4. Fase 0 fechamento — P0.3, P0.4 e P0.5

**P0.3 — CI GitHub Actions** (`.github/workflows/ci.yml`): dois jobs em paralelo (backend com `postgres:16-alpine` service + migrations + pytest; frontend com npm ci + `npx tsc --noEmit`) acionados em push para `main` e em PRs. `concurrency` group cancela execuções superadas. YAML validado por `yaml.safe_load`.

**P0.4 — `.env.example` completo**: 17 chaves documentadas adicionalmente, organizadas por categoria — pool de conexões (`DB_POOL_MIN/MAX`), `DEFAULT_CLINIC_ID`, `FLASK_ENV`, `OPENAI_TIMEOUT`, `GEMINI_TIMEOUT`, `GEMINI_FILES_MODEL`, `TRIAGE_MODEL_OPENAI/GEMINI`, `PROMPT_CACHE_TTL`, `TELEMETRY_*`, `REDIS_URL`, `TASK_*`, `PUBMED_EMAIL`, `PAYMENT_WEBHOOK_SECRET_*` (com exemplos para Mercado Pago, Asaas, PagSeguro), e as 3 chaves do frontend (`NEXT_PUBLIC_API_BASE_URL`, `BACKEND_ORIGIN`, `CANNABIA_API_HOSTPORT`).

**P0.5 — Política de backup/DR + `migrations/down/`**:

- `docs/BACKUP_AND_DISASTER_RECOVERY.md`: RPO/RTO (produção 24h/4h; staging 72h/8h), cobertura (PostgreSQL crítico via Render; ChromaDB rebuilável; legislação re-baixável), export lógico mensal off-site exigido como camada adicional, procedimentos de restauração completa/seletiva/schema-rollback, teste trimestral de recuperação agendado até 2026-05-19, protocolo de comunicação de incidentes com RCA em `docs/rca/YYYY-MM-DD-<slug>.md`. Pontos em aberto registrados: automação do dump mensal, definição de bucket off-site, retenção regulatória do SCC.
- `migrations/down/README.md`: política obrigatória a partir da 022; pré-022 o caminho oficial para voltar é restore-por-backup; procedimento em 2 passos (executar o `.sql` de down + `DELETE FROM schema_migrations WHERE version = 'NNN'`).
- `migrations/down/022_integrity_hardening_down.sql`: reverte as 8 modificações da 022, recria o índice não-unique `idx_triage_links_token_hash` original de 018, documenta que a normalização defensiva de dados (orfaos em patients.user_id zerados, status fora do whitelist convertidos) é **irreversível** via DDL e exige restore.
- `migrations/down/023_timestamp_standardization_down.sql`: converte 18 colunas TIMESTAMPTZ → TIMESTAMP via loop declarativo (mesmo padrão da up), aviso explícito de **perda de fuso-horário**, drop+recreate da view `clinic_members`.

Roundtrip validado em Postgres local: down 023 → down 022 → `DELETE FROM schema_migrations WHERE version IN ('022','023')` → `run_migrations.py` → up 022 + up 023 re-aplicadas. Estado final idêntico ao inicial (4 constraints, 4 hardening indexes, 20 colunas tztz, view recriada). Pytest 124/124.

Commit único em `6a7cfe8 docs+ops(p0.5)`.

### 5. F1.1 — Migration 024 tenants evolution

Avança para a Fase 1 do `docs/BACKLOG_SCC.md`. Escopo da migration 024 mantido estrito à evolução da tabela `tenants`; migração dos FKs `clinic_id → tenant_id` nos child tables fica para migrations subsequentes (F1.2+), respeitando o HANDOFF §4.3 ("adicionar `tenant_id` sem remover `clinic_id`, manter `clinics` como view ou coluna computada").

Sete colunas adicionadas (todas via `ADD COLUMN IF NOT EXISTS`):

| Coluna | Tipo | Observação |
|---|---|---|
| `tenant_type` | VARCHAR(32) NOT NULL CHECK | Whitelist `(clinic, association, doctor)`. Backfill via JOIN em `tenant_types.slug` + fallback defensivo para `'clinic'` em linhas sem slug resolvível. Denormalização de `tenant_type_id` — este FK permanece como fonte de verdade relacional. |
| `trade_name` | VARCHAR(255) | Nome fantasia; backfill de `display_name`. |
| `cnpj` | VARCHAR(14) | UNIQUE partial (`WHERE cnpj IS NOT NULL AND cnpj <> ''`). |
| `incorporation_date` | DATE | Data de constituição. |
| `plan_tier` | VARCHAR(32) NOT NULL DEFAULT `'basic'` CHECK | Whitelist `(basic, pro, premium, sandbox_ready)`. Backfill mapeia `billing_plan` legado: `'starter'→'basic'`; valores já no whitelist SCC preservados; qualquer outro cai em `'basic'` defensivo. |
| `whitelabel_config` | JSONB | Configuração whitelabel por tenant. |
| `is_active` | BOOLEAN GENERATED ALWAYS AS (status = 'active') STORED | Espelho derivado de `status`, requerido pelo doc 25 §4.1. |

Indexes novos: `idx_tenants_type`, `idx_tenants_plan_tier`, `uq_tenants_cnpj` (partial).

38 testes estáticos em `tests/test_migration_024_tenants_evolution.py` cobrindo estrutura, existência de cada coluna, CHECK whitelists (com `sandbox_ready` reservado), ordem correta `backfill → SET NOT NULL`, indexes, idempotência (contagem `ADD COLUMN` ignora comentários; todos os `CREATE INDEX` usam `IF NOT EXISTS`), e retrocompatibilidade (não dropa `tenant_type_id`, `billing_plan`, `display_name`, `status`, `slug`, `legacy_clinic_id`; não cria tabelas do SCC que pertencem a migrations futuras).

Down script em `migrations/down/024_tenants_evolution_down.sql` com aviso explícito de perda informacional ao dropar colunas com dados reais.

Validação em Postgres local: migration aplicada; backfill verificado no tenant único existente (`tenant_type='clinic'`, `trade_name='Clínica Cannabia'`, `plan_tier='basic'` a partir de `billing_plan='starter'`, `is_active=true`). Roundtrip down→re-up bem-sucedido. **Suite: 162 passed** (124 anteriores + 38 novos do 024).

Commit `e160c14 migrations(024): tenants evolution — F1.1 do SCC` pushed para `origin/main`.

## Decisões registradas

1. **Migration 023 precisa manipular views explicitamente quando o loop `ALTER COLUMN TYPE` tocar colunas referenciadas**. Padronizar drop+recreate como primeiro/último bloco da migration em vez de `ALTER VIEW ... RENAME` ou CASCADE (que é agressivo demais). Decisão incorporada ao hardening da 023 e deve orientar futuras migrations que mexam em tipos.

2. **Política de down scripts obrigatória a partir da 022**. Pré-022 fica coberto por restore de backup, não por DDL reversível. Justificativa: migrations antigas têm mudanças de dados que já foram absorvidas em produção; rollback DDL seletivo exige mais análise de dados do que replay de snapshot. Documentado em `migrations/down/README.md`.

3. **Retrocompatibilidade do modelo de tenants é invariante da Fase 1**. A denormalização de `tenant_type_id` → `tenant_type` (VARCHAR CHECK) é aditiva; a FK permanece intocada. `billing_plan` não é removido; `plan_tier` passa a ser o canônico do SCC, mas `billing_plan` continua disponível para código legado. `display_name` e `status` também permanecem como fonte de verdade. `is_active` é coluna gerada, não duplicação mutável.

4. **Mapeamento `billing_plan='starter' → plan_tier='basic'` é a normalização do SCC**. O whitelist do SCC não contém `'starter'`; preserva `basic/pro/premium` e introduz `sandbox_ready` para tenants do programa sandbox. Valores inesperados caem em `'basic'` defensivo para não quebrar o CHECK.

5. **`is_active` como GENERATED STORED é melhor que BOOLEAN + trigger**. Remove classe inteira de bug de divergência entre `status` e `is_active` — o banco recalcula automaticamente a cada UPDATE em `status`. Custo: uma ALTER TABLE com column rewrite (aceitável em `tenants`, tabela pequena).

6. **F1.2 fica para próxima sessão**. F1.1 sozinho é um marco claro (tenants evoluídos + testes + down + aplicação real validada). F1.2 introduz 4 tabelas novas com cross-FK (`associations` referenciando `institutional_documents`) e merece atenção separada.

## Próximos passos

### Imediato (próxima sessão)

1. **F1.2 — migration `025_governance_schema.sql`**: criar `institutional_documents`, `technical_responsibles`, `associations` (referenciando `institutional_documents.id` para statute), e `technical_operational_capacity`. Ordenação de criação dentro da migration importa por causa da FK em `associations.statute_document_id`. Down script + testes estáticos no mesmo commit.
2. Criar `docs/rca/` (diretório vazio com `.gitkeep`) para que o primeiro incidente não precise inventar a estrutura na hora.

### Curto prazo (seguinte)

3. F1.3 — `src/repositories/governance_repository.py`.
4. F1.4 — `src/services/governance_service.py` com validação de elegibilidade automática (natureza jurídica, tempo de constituição, RT habilitado).
5. F1.5 — Blueprint `src/web/routes/governance.py` + geração do Dossiê de Elegibilidade.
6. F1.6 — Skill `check_sandbox_eligibility` no `AgenteRegulatorio`.
7. F1.7 — Frontend `frontend/app/org/sandbox/governance/page.tsx`.
8. F1.8 — `tests/test_governance.py`.

### Fora da Fase 1

9. **~104 arquivos uncommitted**: toda Sprint 6-8 + progressos 8-17 nunca commitados. A sessão de hoje não os tocou para manter histórico limpo. Decidir na próxima sessão se vale fazer um commit único "backfill: sprints 6-8 e progressos 8-17" ou ignorar em definitivo (o estado atual do código já está em produção; a falta de commit é custo de rastreabilidade, não de funcionalidade). Há também a cleanup desta sessão (deletes de logs/scripts antigos) ainda sem commit.
10. Execução do primeiro teste trimestral de recuperação de backup até 2026-05-19.
11. Automação do dump lógico mensal via cron no Render ou GitHub Actions.

## Arquivos relevantes do bloco

### Criados

- `.github/workflows/ci.yml`
- `docs/BACKUP_AND_DISASTER_RECOVERY.md`
- `docs/progresso19_fase0_closure_and_f11_tenants_evolution.md` (este arquivo)
- `migrations/024_tenants_evolution.sql`
- `migrations/down/README.md`
- `migrations/down/022_integrity_hardening_down.sql`
- `migrations/down/023_timestamp_standardization_down.sql`
- `migrations/down/024_tenants_evolution_down.sql`
- `tests/test_migration_024_tenants_evolution.py`

### Modificados

- `.env.example` (17 chaves adicionais)
- `docs/BACKLOG_SCC.md` (P0.3, P0.4, P0.5, F1.1 marcados como Concluído 2026-04-19)
- `docs/runbook.md` (pointer para `migrations/down/` na seção Migrations)
- `migrations/023_timestamp_standardization.sql` (drop+recreate de `clinic_members`)
- `tests/test_migrations_integrity_hardening.py` (+4 testes em `TestMigration023ViewHandling`)

## Bloqueios

Nenhum. Todos os 5 critérios de pronto da Fase 0 (`docs/BACKLOG_SCC.md` §5.1) atendidos localmente; em produção dependem de push + CI verde + execução do preDeployCommand no próximo deploy.

## Primeira missão sugerida para a próxima sessão

Abrir F1.2 escrevendo `migrations/025_governance_schema.sql`. Começar pela tabela `institutional_documents` (sem FKs de saída, só `tenant_id` e `uploaded_by`), depois `technical_responsibles`, depois `associations` (com FK `statute_document_id → institutional_documents.id`) e por fim `technical_operational_capacity`. Cabeçalho da migration com cross-refs ao doc 25 §4.2–4.5. Down script e 30+ testes estáticos no mesmo commit. Aplicar em Postgres local e fazer roundtrip antes de commitar.
