# PHASE 0 — RECONSTRUÇÃO DOCKER CannabIA

**Data:** 2026-05-15
**Pré-requisito:** `RELATORIO_DOCKER_RECON.md` lido e aceito
**Status:** ⛔ AGUARDANDO "GO EXECUÇÃO" após revisão dos 4 blocos abaixo

---

## 🔍 BLOCO 1 — DIVERGÊNCIAS

Tudo que está diferente entre o que o prompt original assumiu e o que a discovery confirmou.

### D1 — Não há docker-compose nem Dockerfile (impacto: ALTO)
- **Esperado:** Reconstruir stack multi-serviço via `docker compose up`.
- **Encontrado:** Apenas 1 container Postgres (`cannabia-postgis`) criado historicamente via `docker run` avulso. Backend Flask, frontend Next.js e ChromaDB rodam no host.
- **Impacto:** A reconstrução vira "rehidratação de banco em 1 container". Tempo real esperado: 10–20 min.

### D2 — Não há Alembic (impacto: MÉDIO)
- **Esperado:** `alembic upgrade head`, verificar `alembic current = 046`.
- **Encontrado:** Runner Python próprio em [src/infra/run_migrations.py](src/infra/run_migrations.py), aplicando arquivos SQL puros 001→046. Tabela de controle: `schema_migrations(version, filename, applied_at, checksum SHA-256)`.
- **Impacto:** Comando muda; conceito de "head" se mantém. Idempotência por checksum.

### D3 — Runner NÃO aceita `--target` nem `--dry-run` (impacto: BAIXO)
- **Esperado (assumido pelo prompt):** Poder parar a aplicação em uma versão específica.
- **Encontrado:** [src/infra/run_migrations.py:110](src/infra/run_migrations.py#L110) — função `run_all()` única, sem args. Aplica tudo o que falta, pula o que já está em `schema_migrations` com mesmo checksum.
- **Impacto:** No nosso caso (DB virgem), aplicar 001→046 em uma única chamada é exatamente o que queremos. Mas é informação importante para o futuro.

### D4 — Migrations 044/045/046 são DDL puro idempotente (impacto: POSITIVO)
- **Esperado:** Risco de purge LGPD acidental.
- **Encontrado:** 044 = `CREATE TABLE IF NOT EXISTS` (purge events + dedup). 045 = `CREATE TABLE LIKE ... INCLUDING ALL` + index. 046 = `ALTER ADD COLUMN IF NOT EXISTS` + UPDATE defensivo (zero rows hoje). **Zero data manipulation. Aplicáveis 100% das vezes sem risco.**
- **Impacto:** Toda a paranoia LGPD do prompt original some desta reconstrução. O purge real só roda via `scripts/retention_audit_logs.py` ou `scripts/purge_audit_pii_pre_a3.py` chamados manualmente.

### D5 — `LGPD_PURGE_KILL_SWITCH` não existe no código (impacto: MÉDIO — conceitual)
- **Esperado:** Variável de ambiente checada pelas migrations ou pelo runtime.
- **Encontrado:** Grep `LGPD_PURGE_KILL_SWITCH|kill_switch|KILL_SWITCH` em `src/` → **0 matches**. O nome real do controle está nos scripts de purge Python (a confirmar quando alguém for tocar nele de novo). Para esta reconstrução, **não tem efeito**.

### D6 — `SENTRY_DSN` existe no runtime mas falta no `.env.example` (impacto: BAIXO)
- **Encontrado:** [src/config.py:58](src/config.py#L58) lê `SENTRY_DSN`. Sentry só inicializa se a variável existir e não-vazia.
- **Impacto:** Como o `.env` local não tem `SENTRY_DSN`, Sentry fica inativo em dev. Zero ruído em produção durante reconstrução.

### D7 — Variáveis runtime extras NÃO documentadas no `.env.example` (impacto: BAIXO)
Confirmadas via grep `os.getenv|os.environ`:
- `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_SAMPLE_RATE`, `SENTRY_TRACES_SAMPLE_RATE`
- `FF_PROMPT_REGISTRY_ADMIN` (feature flag admin UI prompt registry)
- `CASE_AGGREGATE_MIN_K` (knowledge case aggregator)
- `LEGISLATION_DIR` (path para markdowns de legislação)
- `ANCHOR_PROVIDER`, `NOTIFICATION_PROVIDER`, `POLYGON_RPC/KEY/ADDR/NETWORK` (integrações)

Nenhuma dessas é obrigatória para subir o stack base. Todas têm defaults razoáveis ou só ativam features opcionais.

### D8 — Backup recente não existe (impacto: MÉDIO — escopo histórico)
- **Esperado:** Talvez houvesse `*.dump` recente para restore.
- **Encontrado:** `cannabia_pre_scc_I1_.d` e `cannabia_pre_scc_I1_.dump` = **0 bytes**. Não há pasta `backups/` nem `db_backups/`.
- **Impacto:** Reconstrução é greenfield. Anota como follow-up: **investigar por que o pg_dump pré-SCC-I1 falhou silenciosamente** (provável: container parado / disco cheio / auth quebrada).

### D9 — Frontend preservado no host (impacto: POSITIVO)
- **Encontrado:** `frontend/node_modules/` (abr/7), `frontend/.next/` (mai/6), `frontend/tsconfig.tsbuildinfo` (mai/12) — todos presentes.
- **Impacto:** Frontend volta com `npm run dev`. Não precisa de rebuild.

### D10 — Seed prompt_registry tem DRY-RUN como default (impacto: BAIXO — armadilha de operador)
- **Encontrado:** [scripts/seed_prompts.py:71](scripts/seed_prompts.py#L71) — `python -m scripts.seed_prompts` sem `--commit` **NÃO grava nada**. Precisa `--commit` explícito.
- **Impacto:** Se rodar sem `--commit`, a tabela `ai_prompt_versions` fica vazia e o registry cai no fallback hardcoded em silêncio (já é o bug que a Sprint 2 corrigiu — memória S385). **Não repetir.**

---

## ✅ BLOCO 2 — CONFIRMAÇÕES NECESSÁRIAS

Perguntas que precisam de resposta tua antes do GO EXECUÇÃO. Respondi o que descobri sozinho — só falta o que depende da tua decisão.

### Q1 — Como o runner de migrations se comporta?
**Respondido pelo discovery:**
- Comando único: `python -m src.infra.run_migrations` (ou wrapper `python scripts/run_migrations.py`).
- **Não aceita `--target` nem `--dry-run`** — `run_all()` aplica tudo que falta.
- **Tabela de controle:** `schema_migrations(version PRIMARY KEY, filename, applied_at, checksum SHA-256)`, criada bootstrap em `_ensure_tracking_table()` antes do loop.
- **Idempotência forte:** bate checksum SHA-256. Migration já aplicada com mesmo checksum → pula. Checksum mismatch → só WARNING, não bloqueia. Versões duplicadas no diretório → levanta `MigrationVersionConflictError`.
- **Rodar 2x é 100% seguro** — pula com log "Migration X ja aplicada".

**Pergunta para o humano:** ✅ nenhuma. Está claro.

### Q2 — Quem popula o `prompt_registry`?
**Respondido pelo discovery:**
- Script: `scripts/seed_prompts.py` (113 linhas). Importa `_HARDCODED_PROMPTS` de [src/ai/prompt_registry.py](src/ai/prompt_registry.py) e faz `INSERT ... ON CONFLICT (prompt_key, version) DO NOTHING`.
- Idempotente, versão fixa `v1.0.0`, `created_by="system_seed"`.
- **⚠️ Default é dry-run.** Comando real: `python -m scripts.seed_prompts --commit`.
- Pré-requisito: migration 046 aplicada (para colunas `prompt_key`, `is_active`, `created_by`).

**Pergunta para o humano:** ✅ nenhuma. Plano sabe o comando exato.

### Q3 — Variáveis de ambiente reais lidas em runtime
**Respondido pelo discovery (grep `os.getenv|os.environ` em `src/`):**

Variáveis no `.env.example` E lidas em runtime: `DATABASE_URL`, `DB_POOL_MIN/MAX`, `SECRET_KEY`, `ENCRYPTION_KEY`, `SESSION_COOKIE_*`, `FRONTEND_ORIGIN`, `FLASK_ENV`, `META_WHATSAPP_KEY`, `WHATSAPP_*`, `VERIFY_TOKEN`, `DOCTOR_EMAIL`, `EMAIL_*`, `SMTP_*`, `OPENAI_API_KEY/TIMEOUT`, `GOOGLE_API_KEY`, `GEMINI_TIMEOUT`, `GEMINI_FILES_MODEL`, `TRIAGE_MODEL_*`, `PROMPT_CACHE_TTL`, `AI_EXECUTION_MODE`, `TELEMETRY_*`, `REDIS_URL`, `TASK_*`, `PUBMED_EMAIL`, `PAYMENT_*`, `WEBHOOK_*`, `LOGIN_RATE_*`, `CHAT_*`, `TRIAGE_LINK_TTL_S`.

Variáveis lidas em runtime que **FALTAM** no `.env.example`:
| Variável | Onde é lida | Default se ausente |
|---|---|---|
| `SENTRY_DSN` | `src/config.py:58` | vazio → Sentry inativo (OK para dev) |
| `SENTRY_ENVIRONMENT` | `src/config.py:70` | usa `FLASK_ENV` ou `"development"` |
| `SENTRY_SAMPLE_RATE` | `src/config.py:74` | default interno |
| `SENTRY_TRACES_SAMPLE_RATE` | `src/config.py:87` | default interno |
| `FF_PROMPT_REGISTRY_ADMIN` | `src/ai/prompt_registry.py:302` | `"0"` → admin API desabilitada |
| `CASE_AGGREGATE_MIN_K` | `src/knowledge/case_aggregator.py:38` | `"5"` |
| `LEGISLATION_DIR` | `src/knowledge/google_files.py:42` | path default |
| `ANCHOR_PROVIDER`, `NOTIFICATION_PROVIDER`, `POLYGON_*` | integrações | provider mock |

**Variável `LGPD_PURGE_KILL_SWITCH` NÃO existe no código.** O prompt original misturou conceitos — o controle de purge fica nos scripts CLI (`retention_audit_logs.py`, `purge_audit_pii_pre_a3.py`), não em env var.

**Pergunta para o humano:**
- **Q3a:** Quer atualizar o `.env.example` pra adicionar `SENTRY_DSN=` (vazio) e o resto? Recomendo **SIM em PR separado** (não nesta reconstrução), e adicionar à pauta da Sprint 3 (Obs-Harden). **Decisão para esta reconstrução: não fazer agora, não bloqueia.**

### Q4 — Frontend Next.js
**Respondido pelo discovery:**
- `frontend/node_modules/`, `frontend/.next/`, `frontend/tsconfig.tsbuildinfo` — todos preservados.
- `package.json`, `package-lock.json` intactos.
- **Subir com `npm run dev` na porta 3001.** Não precisa rebuild.

**Perguntas para o humano:**
- **Q4a:** O frontend precisa ser validado no smoke test pós-rebuild?
  - **Opção A (recomendada):** Smoke test só backend (curl nos 4 endpoints). Frontend validado depois manualmente.
  - **Opção B:** `npm run dev` + carregar `/dashboard` no browser.
  - Minha sugestão: **A** — reduz superfície de coisas que podem falhar simultaneamente.

### Q5 — Os 4 endpoints Page Tier-1 da Sprint 2
**Respondido pela memória + discovery parcial:**
- `/api/v1/appointments` ✅ (S2865)
- `/api/v1/attendances` ✅ (S2869)
- `/api/v1/conversations` ✅ (S2874)
- 4º endpoint: **provável** `/api/v1/anamnesis-reports` (memória S2867 menciona `anamnesis_repository.list_reports()` extendido com paginação). Vou confirmar lendo `src/web/routes/api_v1.py` durante a execução, antes do smoke test (Passo 6).

**Pergunta para o humano:**
- **Q5a:** Validar 3 confirmados e investigar o 4º durante a execução é OK? Ou queres que eu leia o `api_v1.py` agora pra confirmar antes do GO?
  - Sugestão: **deixar para o início do Passo 6**. Custa nada, fica documentado no relatório executor.

### Q6 — Backup imediato após rebuild
**Respondido pelo discovery + tua proposta:**
- Não há pasta `backups/` no repo (preciso criar).
- Plano: ao final do rebuild, `pg_dump -Fc -h localhost -p 5434 -U <user> -d cannabia -f backups/cannabia_post_rebuild_2026-05-15.dump`.
- **Validação obrigatória:** `Get-Item ... | Length` > 0 + `pg_restore --list backups/<arquivo>.dump` retorna lista não-vazia.

**Perguntas para o humano:**
- **Q6a:** Nome do arquivo de backup OK? Sugestão: `backups/cannabia_post_rebuild_YYYY-MM-DD_HHMM.dump`.
- **Q6b:** Adicionar `backups/` ao `.gitignore`? Dumps de Postgres não devem ir pro git. **Recomendo SIM.**

### Q7 — Decisões operacionais que dependem de ti
Não conseguimos resolver sozinhos — preciso de resposta direta antes do GO:

- **Q7a — Nome do container:** `cannabia-postgis` (igual ao histórico) ou outro nome?
- **Q7b — Nome do volume:** `cannabia_pgdata` (seguindo tua proposta) ou `cannabia_postgres_data` (mais explícito)? Vou com `cannabia_pgdata` se silenciares.
- **Q7c — Credenciais Postgres:** A `DATABASE_URL` atual no `.env` aponta para qual `user/password/database`? Vou precisar passar `POSTGRES_USER/PASSWORD/DB` no `docker run`. **Por segurança, não vou ler o `.env` — me passa os valores via mensagem ou confirma que posso ler.**
- **Q7d — Seeds a executar:**
  - **Mínimo recomendado:** `seed_users.py` (7 users dev) + `seed_prompts.py --commit` (essencial).
  - **Opcional:** `seed_comprehensive.py` (89 KB, dados demo — pode chamar API externa? a verificar).
  - **Não recomendado para esta rodada:** `seed_scc.py` (28 KB, dados SCC), `seed_local_demo.py`. Adicionar se quiser ambiente de demo completo.
  - **Tua escolha?**
- **Q7e — Subir backend e frontend no host após rebuild?**
  - **Backend** é necessário pro smoke test dos 4 endpoints.
  - **Frontend** depende da Q4a acima.
- **Q7f — Limpar `__pycache__` antes de subir backend?** Não estritamente necessário; serve só pra eliminar suspeitas de cache. **Sugestão: pular.**

---

## ⚠️ BLOCO 3 — RISCOS

Como pediste, **pulei** preocupações de LGPD purge (D4 resolveu) e Sentry (D6 resolveu — inativo sem DSN). Adicionei os 2 novos que pediste.

| ID | Risco | Severidade | Mitigação |
|---|---|---|---|
| **R1** | `cannabia-postgis` recriado conflita com porta de outro container | Baixo | Confirmar `vereda_postgres` está em 5433 (já confirmado), `amigao_db` em 55432 (idem), 5434 livre. Reverificar com `netstat -an \| Select-String 5434` antes do `docker run`. |
| **R2** | `seed_comprehensive.py` (89 KB) chama API externa OpenAI/Google e gera custo durante seed | Médio | **Mitigação:** ler header do script antes de executar; se chamar API, pular este seed na 1ª rodada. Limitar à `seed_users` + `seed_prompts --commit` por padrão (ver Q7d). |
| **R3** | Frontend host pegar referência cacheada do banco antigo | Baixo | Não aplicável: banco antigo não existe mais; primeira conexão será limpa. Pular `__pycache__` cleanup é seguro. |
| **R4** | `amigao_..._worker-1` em restart-loop consumir CPU/log durante reconstrução | Baixo | Não tocar; é container de outro projeto. Se incomodar, **perguntar antes** de fazer `docker stop`. |
| **R-NEW-1** | **`pg_dump` pós-rebuild falhar silenciosamente (como os `cannabia_pre_scc_I1_.*` zerados)** | **Alto** | **Validação obrigatória de 3 camadas:** (1) `Get-Item backups/X.dump \| Length` > 0; (2) `pg_restore --list backups/X.dump \| Measure-Object -Line` > 5; (3) `docker exec cannabia-postgis pg_dumpall --version` retorna sucesso antes do dump. Se qualquer uma falhar, **abortar e investigar** (este é o follow-up que motivou a flag amarela). |
| **R-NEW-2** | Runner aplica tudo de uma vez — sem opção de pause em versão intermediária | **Baixo** | Em DB virgem, aplicar 001→046 numa só transação é o cenário ideal. Tabela `schema_migrations` registra cada uma com checksum, então re-runs são 100% seguros. **Validação:** `SELECT version FROM schema_migrations ORDER BY version` deve retornar 47 linhas (001 a 046, mais a 000 da bootstrap). Se o count divergir, **PARAR no PAUSE 2**. |
| **R5** | DRY-RUN como default no `seed_prompts.py` — operador esquecer `--commit` e seguir achando que populou | Médio | Plano usa **`python -m scripts.seed_prompts --commit`** explícito. Validação no PAUSE 3: `SELECT COUNT(*) FROM ai_prompt_versions WHERE active = TRUE` deve retornar 7 (são 7 prompts em `_HARDCODED_PROMPTS`, validado pelo discovery). |
| **R6** | Backend Flask iniciar com `DATABASE_URL` apontando para banco antigo (que não existe mais) | Baixo | Garantir `.env` aponta para `localhost:5434` antes de subir backend. Validar com `python -c "from src.config import DATABASE_URL; print(DATABASE_URL)"`. |

---

## 🎯 BLOCO 4 — PROPOSTA DE EXECUÇÃO

Adotei tua proposta enxuta com pequenos refinamentos (mais validações em pause points, comando exato em cada passo).

```
PASSO 0  → Validações pré-execução (3 itens, paralelo):
            a) docker image ls | grep postgis/postgis:16-3.5-alpine     # confirmar cache local
            b) netstat -an | Select-String ":5434"                       # confirmar porta livre
            c) cat .env | grep DATABASE_URL (sem expor valor)            # confirmar variável existe

PASSO 1  → docker volume create cannabia_pgdata
            (volume nomeado, persiste reboots; não anônimo)

PASSO 2  → docker run -d --name cannabia-postgis \
              --restart unless-stopped \
              -p 5434:5432 \
              -e POSTGRES_USER=<Q7c> \
              -e POSTGRES_PASSWORD=<Q7c> \
              -e POSTGRES_DB=<Q7c> \
              -v cannabia_pgdata:/var/lib/postgresql/data \
              postgis/postgis:16-3.5-alpine

✋ PAUSE 1: validar conexão
   - docker exec cannabia-postgis pg_isready                            # esperar "accepting connections"
   - docker exec -it cannabia-postgis psql -U <user> -d <db> -c '\conninfo'
   - Aguardar tua confirmação visual antes de prosseguir

PASSO 3  → python -m src.infra.run_migrations
            (aplica 000 bootstrap + 001 a 046, registra em schema_migrations)

✋ PAUSE 2: validar schema
   - psql -h localhost -p 5434 -U <user> -d <db> -c \
       "SELECT version, filename FROM schema_migrations ORDER BY version"
   - Esperado: 47 linhas (000 + 001..046 sem gaps)
   - psql ... -c "\dt" deve listar tabelas: patients, medical_history, treatment_plans,
       anamnesis_reports, conversations, ai_audit_logs, ai_audit_purge_events,
       ai_audit_logs_archive, ai_prompt_versions, schema_migrations, etc.
   - Se gap ou count != 47 → ABORTAR, reportar.

PASSO 4  → Seeds (na ordem):
            a) python -m scripts.seed_users          # 7 users dev
            b) python -m scripts.seed_prompts --commit   # ⚠️ --commit OBRIGATÓRIO
            c) [Opcional, Q7d] python -m scripts.seed_comprehensive

✋ PAUSE 3: validar seeds
   - psql ... -c "SELECT username FROM users ORDER BY username"
       → esperado: admin, dono, medico, recepcao, financeiro, admin_clinica, paciente
   - psql ... -c "SELECT prompt_key, version, active FROM ai_prompt_versions WHERE active = TRUE"
       → esperado: 7 linhas, todas active=true, version='v1.0.0'
   - Se contagens divergem → ABORTAR.

PASSO 5  → Subir backend Flask no host
   - Ativar venv: env\Scripts\activate
   - python -m flask --app src.app run --debug --port 5000
   - Rodar em background; aguardar log "Running on http://127.0.0.1:5000"

PASSO 6  → Smoke test 4 endpoints Tier-1
   - Antes: ler src/web/routes/api_v1.py para confirmar o 4º endpoint
     (esperado: /api/v1/anamnesis-reports)
   - curl http://127.0.0.1:5000/api/v1/appointments       → 200 ou 401
   - curl http://127.0.0.1:5000/api/v1/attendances        → 200 ou 401
   - curl http://127.0.0.1:5000/api/v1/conversations      → 200 ou 401
   - curl http://127.0.0.1:5000/api/v1/anamnesis-reports  → 200 ou 401 (a confirmar)
   - Também curl /health (path exato a confirmar)         → 200
   - Logs do backend: sem ERROR/CRITICAL

PASSO 7  → Backup inicial validado (R-NEW-1)
   - mkdir backups (se não existir)
   - echo "*.dump" >> .gitignore (se ainda não estiver)
   - $stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
   - docker exec cannabia-postgis pg_dump -Fc -U <user> -d <db> > backups/cannabia_post_rebuild_$stamp.dump
   - Validações OBRIGATÓRIAS:
       (1) (Get-Item backups/cannabia_post_rebuild_$stamp.dump).Length -gt 0
       (2) pg_restore --list backups/cannabia_post_rebuild_$stamp.dump | Measure-Object -Line  (> 5)
       (3) Reportar SHA-256 do dump pra registro
   - Se qualquer validação falhar → ABORTAR, registrar como bug crítico
     (este é o ponto do flag amarelo).

PASSO 8  → Gerar RELATORIO_DOCKER_RECON_EXEC.md com:
   - Timestamps de cada passo
   - Output dos checkpoints
   - Hash do dump pós-rebuild
   - Lista das 47 migrations aplicadas (snapshot de schema_migrations)
   - Status final: ambiente verde / amarelo / vermelho
   - Follow-up flags:
       * Investigar por que cannabia_pre_scc_I1_.dump nasceu com 0 bytes
       * .env.example não tem SENTRY_DSN nem outras vars runtime (Sprint 3 Obs-Harden)
       * LGPD_PURGE_KILL_SWITCH é nome fantasma — controle real está em CLI dos scripts purge
```

### Estimativa de tempo
- Sem percalços: 10–15 minutos (pause points humanos somam mais 10–20 min).
- Em caso de erro num passo: rollback é trivial (`docker stop cannabia-postgis && docker rm cannabia-postgis && docker volume rm cannabia_pgdata` + recomeçar).

### Plano de rollback (se algo falhar)
| Passo onde falhou | Como reverter |
|---|---|
| 1–2 (volume/container) | `docker rm -f cannabia-postgis; docker volume rm cannabia_pgdata` |
| 3 (migrations) | `docker volume rm` apaga tudo; voltar ao Passo 1 |
| 4 (seeds) | Idem: `seed_users` e `seed_prompts` são idempotentes, mas se pior caso, refaz do volume |
| 5–6 (backend/smoke) | Backend rodando no host: `Ctrl+C`. Postgres intacto, sem efeito colateral |
| 7 (backup) | Excluir arquivo `.dump` corrompido e investigar antes de retry |

---

## ⛔ FIM DA PHASE 0 — AGUARDANDO "GO EXECUÇÃO"

**Decisões que preciso de ti antes de executar (compactadas):**
1. **Q4a** — Frontend no smoke test? (A: só backend / B: backend + frontend)
2. **Q6a/Q6b** — Nome do backup + adicionar `backups/` ao `.gitignore`?
3. **Q7a** — Nome do container: `cannabia-postgis` ou outro?
4. **Q7b** — Nome do volume: `cannabia_pgdata` (default meu) ou outro?
5. **Q7c** — Credenciais Postgres: passar via mensagem ou autorizar leitura do `.env`?
6. **Q7d** — Seeds: mínimo (`seed_users` + `seed_prompts --commit`) ou incluir `seed_comprehensive`?
7. **Q7e** — Subir backend (e frontend) no host após rebuild?

Mande as respostas + "GO EXECUÇÃO" para eu prosseguir.
