# RELATÓRIO DE RECONSTRUÇÃO DOCKER — CannabIA

**Data:** 2026-05-15
**Coordenador:** Claude (Opus 4.7)
**Fase:** 1 — DISCOVERY (somente leitura, zero mutação)
**Status ao final desta fase:** ⛔ AGUARDANDO "GO PHASE 0"

---

## 🚨 SUMÁRIO EXECUTIVO — LEIA ANTES DE TUDO

O prompt original assume uma stack Docker mais robusta do que a realidade do repositório.
**Não há `docker-compose.yml`, não há `Dockerfile`, não há alembic.** A topologia real é:

- **Postgres rodava em UM container Docker avulso** (`cannabia-postgis`, postgis/postgis:16-3.5-alpine, porta 5434), criado historicamente via `docker run` manual.
- **Backend Flask roda no host**, em virtualenv local (`./env`), via `python -m flask` ou Gunicorn.
- **Frontend Next.js roda no host**, via `npm run dev` na porta 3001.
- **ChromaDB roda local em arquivo** (`./chroma_db/`).
- **Migrations são SQL puro** numeradas 000→046 em `./migrations/`, aplicadas por runner próprio em `src/infra/run_migrations.py`.

Portanto, "reconstruir o ambiente Docker" significa, na prática:
**recriar 1 (um) container Postgres + popular o banco com migrations + seeds.**

Vários itens do prompt original (alembic head, healthcheck do compose, depends_on, kill switch nas migrations) **não se aplicam** ou se aplicam de forma diferente. As divergências estão detalhadas na Seção 11.

---

## 1. INVENTÁRIO DOCKER NO CÓDIGO

| Item buscado | Resultado |
|---|---|
| `docker-compose*.yml` | **NÃO EXISTE** no projeto |
| `Dockerfile*` | **NÃO EXISTE** no projeto |
| `.dockerignore` | **NÃO EXISTE** no projeto |
| `.dockerfiles/` | **NÃO EXISTE** no projeto |
| Referência a Docker em scripts | Apenas em `analise-disco.ps1` (script de análise de disco, somente leitura) |

**Implicação:** Não há serviços Docker declarados versionados no repo. A criação do `cannabia-postgis` foi feita historicamente via `docker run` manual (memória `project_local_db_setup`). Não há networks, healthchecks ou depends_on para reconstruir — só 1 container avulso.

---

## 2. CONFIGURAÇÃO DE AMBIENTE (`.env*`)

### Arquivos encontrados
- `.env` (1245 bytes, abr/20) — em uso local
- `.env.example` (7496 bytes, mai/1) — referência canônica

### Chaves presentes no `.env` local (apenas chaves, sem valores)
```
OPENAI_API_KEY, GOOGLE_API_KEY, DATABASE_URL, META_WHATSAPP_KEY,
WHATSAPP_PHONE_NUMBER_ID, RECIPIENT_PHONE, DOCTOR_EMAIL,
EMAIL_FROM, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT,
SESSION_COOKIE_SECURE, SECRET_KEY, WHATSAPP_APP_SECRET
```

### Chaves presentes no `.env.example` (canônico, completo)
```
DATABASE_URL, DB_POOL_MIN, DB_POOL_MAX, DEFAULT_CLINIC_ID,
SECRET_KEY, ENCRYPTION_KEY, SESSION_COOKIE_SECURE,
SESSION_COOKIE_SAMESITE, MAX_CONTENT_LENGTH, FRONTEND_ORIGIN,
FLASK_ENV, WEBHOOK_RATE_LIMIT, WEBHOOK_RATE_WINDOW_S,
LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW_S, CHAT_SESSION_TTL_S,
CHAT_CLEANUP_INTERVAL_S, TRIAGE_LINK_TTL_S, META_WHATSAPP_KEY,
WHATSAPP_PHONE_NUMBER_ID, RECIPIENT_PHONE, WHATSAPP_APP_SECRET,
WHATSAPP_WEBHOOK_REQUIRE_SIGNATURE, VERIFY_TOKEN, DOCTOR_EMAIL,
EMAIL_FROM, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT,
OPENAI_API_KEY, OPENAI_TIMEOUT, GOOGLE_API_KEY, GEMINI_TIMEOUT,
GEMINI_FILES_MODEL, TRIAGE_MODEL_OPENAI, TRIAGE_MODEL_GEMINI,
PROMPT_CACHE_TTL, AI_EXECUTION_MODE, TELEMETRY_FOLLOWUP_SEND_HOUR,
TELEMETRY_DISPATCH_INTERVAL_M, TELEMETRY_IOT_BATCH_MAX,
REDIS_URL, TASK_RESULT_TTL, TASK_FAILURE_TTL, TASK_DEFAULT_TIMEOUT,
TASK_MAX_RETRIES, PUBMED_EMAIL, PAYMENT_WEBHOOK_REQUIRE_SIGNATURE,
PAYMENT_WEBHOOK_SECRET_MERCADOPAGO, PAYMENT_WEBHOOK_SECRET_ASAAS,
PAYMENT_WEBHOOK_SECRET_PAGSEGURO, NEXT_PUBLIC_API_BASE_URL,
BACKEND_ORIGIN, CANNABIA_API_HOSTPORT
```

### Observações críticas
- **`LGPD_PURGE_KILL_SWITCH`** mencionado no prompt **NÃO existe** no `.env.example` nem foi encontrado em `src/` (grep `LGPD_PURGE_KILL_SWITCH|kill_switch` retornou 0 matches). Pode ser que a memória da Sprint 2 esteja se referindo a uma variável diferente — investigar nos scripts `retention_audit_logs.py` e `purge_audit_pii_pre_a3.py` antes da execução.
- **`SENTRY_DSN`** mencionado no prompt **NÃO existe** no `.env.example`. Sprint 2 Track Obs adicionou Sentry — variável deve estar em código de `src/infra/observability.py` (a verificar).
- `REDIS_URL` está no `.env.example` mas Redis **não está rodando nem é mencionado no README como obrigatório** — provavelmente opcional para Celery (que também não está dockerizado).

---

## 3. ESTADO ATUAL DO DOCKER (RUNTIME)

### Volumes (`docker volume ls`)
```
amigao_do_meio_ambiente_mempalace_data
amigao_do_meio_ambiente_minio_data
amigao_do_meio_ambiente_postgres_data
amigao_do_meio_ambiente_redis_data
amigo_do_meio_ambiente_minio_data
amigo_do_meio_ambiente_postgres_data
amigo_do_meio_ambiente_redis_data
enjoyfun_backend_logs
enjoyfun_mempalace_data
enjoyfun_redis_data
vereda_evolution_instances
vereda_minio_data
vereda_postgres_data
vereda_redis_data
```
**🚨 NENHUM volume contém o prefixo `cannabia_`.** Todos os volumes vivos pertencem a outros projetos (amigao, vereda, enjoyfun). Os "2 volumes não-conectados, 231,7 MB" deletados no incidente provavelmente eram os do CannabIA.

### Containers (`docker ps -a`)
```
vereda_postgres                    pgvector/pgvector:pg18         up 14h    :5433
vereda_minio_init                  minio/mc                       exited
amigao_do_meio_ambiente-api-1      amigao..._ambiente-api         up 21s    :8000
vereda_evolution                   evoapicloud/evolution-api      up 14h    :8083
amigao_do_meio_ambiente-worker-1   amigao..._ambiente-worker      restarting (loop)
amigao_do_meio_ambiente-client     amigao..._ambiente-client      up 14h    :3000
amigao_do_meio_ambiente-db-1       amigao..._ambiente-db          exited    :55432
vereda_redis                       redis:7-alpine                 up 14h    :6380
vereda_minio                       minio/minio                    up 14h    :9100,9101
amigao_..._ambiente-redis-1        redis:7-alpine                 exited    :6379
amigao_..._ambiente-minio-1        minio/minio                    exited    :9000-9001
```
**🚨 NENHUM container `cannabia-postgis` existe** — foi limpo pelo `docker container prune`.

⚠️ **Conflito potencial de portas:** `vereda_postgres` ocupa **5433**, mas o `cannabia-postgis` esperado roda em **5434** (memória `project_local_db_setup`). Sem conflito direto, mas confirmar.
⚠️ **`amigao_do_meio_ambiente-worker-1`** está em loop de restart — não é do CannabIA, mas pode estar consumindo CPU/log.

### Imagens (`docker image ls`)
- `postgis/postgis:16-3.5-alpine` ✅ **PRESERVADA** — sem necessidade de re-pull
- `redis:7-alpine` ✅ presente (não usado pelo CannabIA dockerizado)
- Nenhuma imagem com tag `cannabia_*` existe (esperado, já que não há Dockerfile)

### Networks
- Nenhuma network do CannabIA (esperado).

---

## 4. INVENTÁRIO DE MIGRATIONS

**Caminho:** `./migrations/` (não `backend/alembic/versions/` — não há alembic).
**Runner:** `src/infra/run_migrations.py`, wrapper CLI em `scripts/run_migrations.py`.
**Formato:** SQL puro, idempotente (usa `IF NOT EXISTS`).

### Lista completa em ordem (47 arquivos: 000 → 046)
```
000_migration_tracking.sql
001_initial_schema.sql
002_whatsapp_sessions.sql
003_anamnesis_reports.sql
004_tenants_foundation.sql
005_patient_timeline_foundation.sql
006_medical_records_foundation.sql
007_add_foreign_keys.sql
008_audit_trail.sql
009_knowledge_versions.sql
010_billing_foundation.sql
011_campaign_templates.sql
012_prescriptions_orders.sql
013_telemetry_timeseries.sql
014_missing_tables_and_columns.sql
015_users_enhancement.sql
016_knowledge_catalog.sql
017_knowledge_monitors.sql
018_triage_links.sql
019_conversations.sql
020_tenant_extensions.sql
021_payment_requests_transactions.sql
022_integrity_hardening.sql
023_timestamp_standardization.sql
024_tenants_evolution.sql
025_governance_schema.sql
026_members_schema.sql
027_quality_schema.sql
028_traceability_schema_base.sql
029_traceability_hash_chaining.sql
030_traceability_triggers.sql
031_pharmacovigilance_schema.sql
032_regulatory_schema.sql
033_crypto_schema.sql
034_review_workflows.sql
035_indexes_and_performance.sql
036_views_and_helpers.sql
037_seed_data_sandbox.sql
038_user_roles_refinement.sql
039_tenant_settings.sql
040_knowledge_global_authorship.sql
041_knowledge_case_aggregates.sql
042_patient_app_honesty.sql
043_prescritor_telemetry.sql
044_audit_purge_events.sql           ← LGPD Sprint 2
045_audit_archive_retention.sql      ← LGPD Sprint 2
046_prompt_registry_alignment.sql    ← Reg Sprint 2 (head atual)
```
+ pasta `migrations/down/` (rollbacks).

### Head atual: **046_prompt_registry_alignment.sql** ✅ confere com Sprint 2.

### Auditoria das migrations 044/045/046
- **044** (`audit_purge_events.sql`): apenas `CREATE TABLE IF NOT EXISTS ai_audit_purge_events` + `ai_audit_purge_processed_ids` + 1 index. **Zero data manipulation. Zero risco de purge ao aplicar.**
- **045** (`audit_archive_retention.sql`): apenas `CREATE TABLE LIKE ai_audit_logs INCLUDING ALL` + 1 index composto. **Zero deletes. Zero risco.**
- **046** (`prompt_registry_alignment.sql`): `ALTER TABLE ADD COLUMN IF NOT EXISTS` + `UPDATE` defensivo (zero rows hoje) + 1 unique index. **Idempotente. Zero risco.**

**Conclusão:** As 3 migrations finais são puramente schema (DDL) e idempotentes. Não há gatilho de purge embutido — o purge real só roda quando alguém executa o script `scripts/retention_audit_logs.py` ou `scripts/purge_audit_pii_pre_a3.py`.

---

## 5. SEEDS E FIXTURES

**Caminho:** `./scripts/seed_*.py` + `scripts/SEED_README.md`.

### Scripts disponíveis
| Script | Tamanho | Propósito |
|---|---|---|
| `seed_users.py` | 6.3 KB | 7 usuários dev (admin, dono, medico, recepcao, financeiro, admin_clinica, paciente) — memória `project_dev_credentials` |
| `seed_prompts.py` | 3.3 KB | Popula `ai_prompt_versions` com prompts canônicos da Sprint 2 |
| `seed_scc.py` | 28.7 KB | SCC (sistema de classificação clínica) |
| `seed_local_demo.py` | 18.2 KB | Dados demo simples |
| `seed_comprehensive.py` | 89.9 KB | Seed completo (pacientes, anamneses, plans, etc.) |
| `seed_test_data.py` | 7.6 KB | Fixtures para testes |
| `setup_local.py` | 2.2 KB | Orquestrador: migrations → seed_users → seed_comprehensive |

### Idempotência
- `setup_local.py` usa `seed_users` + `seed_comprehensive` em sequência. `seed_comprehensive` é opcional (try/except ImportError).
- A maioria dos scripts não foi verificada para idempotência neste discovery — recomendado **rodar 1x em DB virgem** (que é o cenário atual).

### Pre-requisito Sprint 2: `seed_prompts.py`
Migration 046 adiciona colunas `prompt_key`, `is_active`, `created_by`, `model`, `agent_name` em `ai_prompt_versions`. O registry DB-first só funciona se `seed_prompts.py` for executado depois das migrations (caso contrário cai no fallback hardcoded — comportamento observado e corrigido na Sprint 2, memória S385).

---

## 6. BACKUPS E DUMPS

| Arquivo | Tamanho | Status |
|---|---|---|
| `cannabia_pre_scc_I1_.d` | **0 bytes** | **VAZIO — INÚTIL** |
| `cannabia_pre_scc_I1_.dump` | **0 bytes** | **VAZIO — INÚTIL** |

**🚨 Não há backup recente do banco local utilizável.** Os arquivos `cannabia_pre_scc_I1_.*` na raiz (criados 11/05 21:58) parecem ter sido `pg_dump` interrompido ou falhado (tamanho zero).

**Implicação:** A reconstrução **NÃO PODE restaurar dados de dev locais** que existiam pré-incidente. Vai começar com banco virgem + migrations + seeds.

---

## 7. HEALTHCHECKS E ENDPOINTS DE VALIDAÇÃO

### Endpoint de saúde
Localização exata não confirmada neste discovery (grep com timeout). Padrão Flask sugere `/health` ou `/api/v1/health`. **Confirmar no Phase 0.**

### 4 Endpoints Page Tier-1 da Sprint 2 (memória S2865, S2869, S2874)
1. `GET /api/v1/appointments` — paginação canônica ✅
2. `GET /api/v1/attendances` — paginação canônica ✅
3. `GET /api/v1/conversations` — paginação canônica ✅
4. **4º endpoint:** provável `GET /api/v1/anamnesis-reports` (memória S2867 cita `anamnesis_repository.list_reports()` atualizado com paginação) — **confirmar antes do smoke test**.

---

## 8. DEPENDÊNCIAS EXTERNAS — NÃO TOCAR

| Dependência | Status | Ação |
|---|---|---|
| **Render produção** | Operacional, não afetada pelo incidente | **PROIBIDO** chamar, fazer deploy, rodar migration remota |
| **Sentry** | DSN local desconhecido — não há `SENTRY_DSN` no `.env.example` | Decidir no Bloco 2 (provavelmente desabilitar local) |
| **Render Cron Job (retention)** | Roda `retention_audit_logs.py` em produção | Não afeta reconstrução local |
| **Meta WhatsApp API** | Webhook de produção | Não afeta reconstrução local |

---

## 9. STACK CONFIRMADA VIA INVENTÁRIO

| Camada | Tecnologia real (não a do prompt) |
|---|---|
| Backend | **Flask 3.x + Gunicorn + Eventlet** (não FastAPI) — roda no host, virtualenv `./env` |
| Linguagem | Python 3.12+ |
| DB | **PostgreSQL 16 + PostGIS** (postgis/postgis:16-3.5-alpine) — **único container Docker** |
| pgvector | NÃO (a base usa ChromaDB local, não pgvector) |
| Redis | Variável `REDIS_URL` existe mas Redis não está rodando — opcional |
| Celery | Não dockerizado — possivelmente não em uso ativo local |
| Frontend | Next.js 14 App Router — roda no host na porta **3001** (dev) ou 3000 (prod) |
| Reverse proxy / nginx | Não há |
| Vetorial | **ChromaDB local em arquivo** (`./chroma_db/`) — não em container |
| Deploy prod | Render via `render.yaml` |

---

## 10. DOCUMENTAÇÃO INTERNA EXISTENTE

- `README.md` — quick start local (Python venv + DB acessível via `DATABASE_URL`, sem menção a Docker)
- `CLAUDE.md` — manual de contexto técnico
- `docs/00..20` — série documental oficial
- `scripts/SEED_README.md` — instruções de seeds
- **Não há `DOCKER.md` nem `DEVELOPMENT.md`.**
- Memórias auto-mem relevantes: `project_local_db_setup`, `project_dev_credentials`, `project_frontend_ports`, `project_sprint_progress`, `project_sprint_1_cannabia`, `project_sprint_2_cannabia`.

---

## 11. COMPARAÇÃO: ESPERADO (PROMPT) vs ENCONTRADO

| Aspecto | Prompt assume | Realidade | Impacto |
|---|---|---|---|
| Docker Compose | Existe `docker-compose*.yml` com serviços, networks, depends_on, healthchecks | **NÃO EXISTE.** Só `docker run` manual de 1 container | **ALTO** — todo o capítulo de "compose up" cai por terra |
| Stack containerizada | Backend + DB + Redis + Celery + Frontend em containers | **Apenas Postgres em container.** Resto roda no host | **ALTO** — smoke test do compose não se aplica |
| Alembic | "alembic upgrade head", verificar "current = 046" | **Não há alembic.** Runner SQL próprio em `src/infra/run_migrations.py` | **MÉDIO** — comando muda, conceito de "head" se mantém (046) |
| LGPD kill switch nas migrations 044/045 | Pode disparar purge acidentalmente | **044/045 são DDL puro, zero data ops.** Purge só roda via script Python manual | **BAIXO** — risco original superestimado |
| `LGPD_PURGE_KILL_SWITCH` no .env | Variável existe e deve ser checada | **Não encontrada** em `.env.example` nem em grep no `src/` | **MÉDIO** — confirmar nome real da variável antes de checar |
| `SENTRY_DSN` no .env | Existe e gera ruído se mal configurado | **Não está no `.env.example`** | **BAIXO** — Sentry só ativa se a var existir |
| Backup recente | Pode existir backup utilizável | **Os 2 dumps `cannabia_pre_scc_I1_.*` estão com 0 bytes** | **MÉDIO** — confirma que perda de dados de dev é total, mas DB era de dev local sem dados críticos |
| Volume sobrevivente | Pode existir | **Nenhum volume com prefixo `cannabia_*`** vivo | **CERTEZA** — não há nada para preservar; reconstrução é greenfield |
| 4 endpoints Page Tier-1 | Sabidos | 3 confirmados (appointments/attendances/conversations) + 4º muito provável `anamnesis-reports` | **BAIXO** — confirmar no smoke test |
| Imagem base preservada | Incerto | **`postgis/postgis:16-3.5-alpine` está no cache** | **POSITIVO** — sem precisar de pull |

### O que precisa ser recriado (lista mínima e suficiente)
1. ✅ **1 container Docker:** `cannabia-postgis` na porta 5434, imagem `postgis/postgis:16-3.5-alpine`, com volume nomeado (sugiro `cannabia_postgres_data`).
2. ✅ **Banco populado:** migrations 000→046 + seeds (decidir quais).
3. ✅ **`.env` local revisado:** confirmar que `DATABASE_URL` aponta para `localhost:5434` e que credenciais conferem.

### O que NÃO precisa ser recriado
- ❌ Nenhum docker-compose, Dockerfile, ou rede Docker.
- ❌ Nenhum container para backend/frontend/redis/celery (rodam no host).
- ❌ Nenhuma imagem custom (não há).

---

## 12. RISCOS IDENTIFICADOS

| ID | Risco | Severidade | Mitigação |
|---|---|---|---|
| R1 | Confundir o `cannabia-postgis` recriado com o `vereda_postgres` (porta 5433) ou `amigao_..._db-1` (porta 55432) | Médio | Validar `psql -h localhost -p 5434` aponta para o container correto antes de migrations |
| R2 | Aplicar 044/045 disparar algo destrutivo | Baixíssimo | Já auditado nesta fase — são puramente DDL idempotente |
| R3 | `seed_comprehensive.py` (89 KB) não ser idempotente e duplicar dados se rodado 2x | Médio | DB virgem — 1ª execução só; se falhar no meio, drop + recriar volume é trivial (não há dados a preservar) |
| R4 | Seeds executarem com chaves OpenAI/Google reais e gerarem custo | Baixo | `seed_comprehensive` provavelmente não chama API externa (verificar antes) |
| R5 | Conflito de porta 5434 com outro serviço | Baixo | `docker ps -a` mostrou que nenhum container usa 5434; verificar `netstat` antes do `docker run` |
| R6 | Sentry produção receber eventos de reconstrução local | Baixo | `SENTRY_DSN` não está no `.env.example`; só ativa se for adicionado manualmente — não adicionar |
| R7 | `amigao_..._worker-1` em restart-loop continuar consumindo CPU durante reconstrução | Baixo | Não é do CannabIA; alertar usuário ou parar com `docker stop` (não destrutivo, container do outro projeto) |
| R8 | Frontend ou backend host pegar referência cacheada do banco antigo | Médio | Limpar `__pycache__/` opcional; reiniciar backend é suficiente |

---

## 13. DEPENDÊNCIAS BLOQUEANTES

- **Imagens custom:** nenhuma. `postgis/postgis:16-3.5-alpine` já está no cache local — zero tempo de build/pull.
- **Variáveis obrigatórias sem default seguro:** `DATABASE_URL` precisa apontar para `localhost:5434/cannabia` (ou similar) com user/password do container; confirmar com usuário se a senha do `.env` atual ainda corresponde ao que será usado no `docker run`.
- **Pacotes Python:** `requirements.txt` (1245 bytes — nada exótico). Virtualenv `./env` pode já estar pronta — confirmar antes de reinstalar.
- **Pacotes Node:** `frontend/node_modules` provavelmente preservado (não está no escopo desta reconstrução Docker).

---

## 14. PLANO DE RECONSTRUÇÃO PROPOSTO

### Sequência sugerida (sujeita a confirmação no Phase 0)

```
PASSO 0  → Snapshot do estado atual (já feito em parte: docker ps -a, volume ls, image ls salvos
            neste relatório). Salvar versão TXT separada se quiser histórico exato.

PASSO 1  → Confirmar com usuário:
              a) Nome exato do container desejado (sugiro: cannabia-postgis)
              b) Nome do volume (sugiro: cannabia_postgres_data)
              c) Credenciais Postgres (user/password/database) — devem casar com .env atual
              d) Quais seeds rodar
              e) Sentry: desabilitar local? (sugiro sim)

PASSO 2  → docker run -d --name cannabia-postgis \
              -p 5434:5432 \
              -e POSTGRES_USER=<user> -e POSTGRES_PASSWORD=<pwd> -e POSTGRES_DB=<db> \
              -v cannabia_postgres_data:/var/lib/postgresql/data \
              --restart unless-stopped \
              postgis/postgis:16-3.5-alpine

PASSO 3  → Aguardar Postgres ficar pronto (pg_isready ou docker exec ... psql -c 'SELECT 1')
✋ PAUSE: validar conexão antes de migrations

PASSO 4  → Validar .env aponta para localhost:5434 e credenciais conferem
PASSO 5  → python scripts/run_migrations.py
✋ PAUSE: confirmar 47 migrations aplicadas (000→046), tabela schema_migrations populada

PASSO 6  → python scripts/setup_local.py (ou seeds individuais conforme decidido)
              - seed_users
              - seed_prompts (essencial para Sprint 2 Track Reg funcionar)
              - seed_comprehensive (opcional, dados demo)
✋ PAUSE: validar ai_prompt_versions populado, user admin existe

PASSO 7  → (Opcional) Subir backend e frontend no host se forem ser usados:
              - backend: python -m flask --app src.app run --debug (porta 5000)
              - frontend: cd frontend && npm run dev (porta 3001)

PASSO 8  → Smoke test:
              - psql -h localhost -p 5434 -U <user> -d <db> -c '\dt' (tabelas existem)
              - psql ... -c 'SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1'
              - Se backend rodando: curl /health → 200, /api/v1/appointments → 200/401
✋ PAUSE: confirmar verde

PASSO 9  → Gerar RELATORIO_DOCKER_RECON_EXEC.md
```

### Estimativa de tempo total
- Sem build de imagem (já cached) e sem download externo: **5–15 minutos** para um cenário sem percalços.
- Com pause points humanos: **30–45 minutos**.

---

## CRITÉRIOS DE SUCESSO (revisados à realidade)

- [ ] Container `cannabia-postgis` rodando e `healthy` (via `pg_isready`)
- [ ] Volume `cannabia_postgres_data` criado e persistente
- [ ] Tabela `schema_migrations` contém versões `000`–`046`
- [ ] Tabela `ai_prompt_versions` populada (prompts da Sprint 2)
- [ ] Usuário `admin` existe e consegue logar
- [ ] Backend (se subido) responde `/health` 200
- [ ] 4 endpoints Tier-1 respondem 200/401 (não 5xx)
- [ ] Logs do container Postgres sem `FATAL` ou `PANIC`
- [ ] Sentry não recebeu nenhum evento de reconstrução
- [ ] `RELATORIO_DOCKER_RECON_EXEC.md` documenta tudo

---

## RESTRIÇÕES INVIOLÁVEIS (reforçadas)

1. ❌ **NÃO tocar em produção (Render)** — nenhuma chamada, nenhum deploy
2. ❌ **NÃO executar `docker volume rm` em nada** sem confirmação explícita do usuário (mesmo que pareça órfão)
3. ❌ **NÃO commitar nada** durante a reconstrução
4. ❌ **NÃO criar PR automático**
5. ❌ **NÃO pular pause points**
6. ❌ **NÃO parar os containers de outros projetos** (vereda, amigao, enjoyfun) sem autorização

---

## ⛔ FIM DA FASE 1 — AGUARDANDO "GO PHASE 0"

Próxima fase: `PHASE0_DOCKER_RECON.md` com os 4 blocos (Divergências, Confirmações Necessárias, Riscos, Proposta de Execução).
