# RELATÓRIO DE EXECUÇÃO — Reconstrução Docker CannabIA

**Data:** 2026-05-15
**Operador:** Claude (Opus 4.7) sob coordenação humana
**Status final:** 🟢 **VERDE** — ambiente reconstruído, validado, e backupado
**Tempo total ativo:** ~30 minutos (incluindo 3 pause points humanos)
**Documentos relacionados:**
- [RELATORIO_DOCKER_RECON.md](RELATORIO_DOCKER_RECON.md) — Discovery
- [PHASE0_DOCKER_RECON.md](PHASE0_DOCKER_RECON.md) — Plano aprovado
- [BUGS_DETECTED.md](BUGS_DETECTED.md) — BUG-001 (dumps zerados)

---

## SUMÁRIO EXECUTIVO

Reconstrução completa do ambiente Docker local do CannabIA após o incidente de 14/05/2026. Em vez de uma stack complexa, o que foi reconstruído foi:

- ✅ **1 container Docker** (`cannabia-postgis`, postgis 16-3.5-alpine, porta 5434)
- ✅ **1 volume nomeado** (`cannabia_pgdata`)
- ✅ **46 migrations SQL** aplicadas (001..046, incluindo Sprint 2 LGPD + Reg)
- ✅ **7 prompts** semeados em `ai_prompt_versions` (registry DB-first ativo)
- ✅ **Backend Flask** subindo, todos componentes healthy
- ✅ **3 endpoints Tier-1** respondendo 401 (auth gate, não 5xx)
- ✅ **Backup pós-rebuild validado** triplamente (Length, pg_restore --list, SHA-256)

Tudo isso sem tocar produção (Render), sem commit de código, e sem deletar volumes sobreviventes de outros projetos.

---

## ARTEFATOS GERADOS

| Caminho | Conteúdo |
|---|---|
| `backups/postgres/cannabia_post_rebuild_20260515_2023.dump` | Backup inicial validado (408.382 bytes, SHA-256 `59F1...AD43`) |
| `backups/postgres/CHECKSUMS.txt` | Registro SHA-256 do dump |
| `backups/postgres/incident_20260514_zero_dumps/` | 2 dumps zerados pré-incidente movidos como evidência (Ajuste B) |
| `backups/postgres/snapshots_pre_rebuild_20260515/docker_ps_a.txt` | Snapshot containers pré-rebuild |
| `backups/postgres/snapshots_pre_rebuild_20260515/docker_volume_ls.txt` | Snapshot volumes pré-rebuild |
| `backups/postgres/snapshots_pre_rebuild_20260515/docker_image_ls.txt` | Snapshot imagens pré-rebuild |
| `backups/postgres/snapshots_pre_rebuild_20260515/docker_network_ls.txt` | Snapshot networks pré-rebuild |
| `backups/postgres/snapshots_pre_rebuild_20260515/migrations_run.log` | Log da aplicação das 46 migrations |
| `backups/postgres/snapshots_pre_rebuild_20260515/seed_prompts.log` | Log do seed (7 inserted, 0 skipped) |
| `backups/postgres/snapshots_pre_rebuild_20260515/backend.log` | Log do Flask backend |
| `BUGS_DETECTED.md` | BUG-001: dumps zerados pré-incidente |

---

## EXECUÇÃO PASSO A PASSO

### Ajuste B (pré-PASSO 0): mover dumps zerados como evidência

- Pasta criada: `backups/postgres/incident_20260514_zero_dumps/`
- `cannabia_pre_scc_I1_.d` (0 bytes, 2026-05-11 21:58:57) movido
- `cannabia_pre_scc_I1_.dump` (0 bytes, 2026-05-11 21:58:08) movido
- `BUGS_DETECTED.md` criado com BUG-001 (severidade ALTA, investigação pendente)

### PASSO 0 — Snapshot Docker + validações pré-execução

| Check | Resultado |
|---|---|
| `postgis/postgis:16-3.5-alpine` no cache local | ✅ presente |
| Porta 5434 livre | ✅ livre |
| `.env` contém `DATABASE_URL` | ✅ parseado: host=127.0.0.1, port=5434, db=cannabia, user/pwd não-vazios |
| Snapshot Docker (ps, volumes, images, networks) | ✅ 4 arquivos em `snapshots_pre_rebuild_20260515/` |

### PASSO 1 — `docker volume create cannabia_pgdata`

```
cannabia_pgdata  driver=local  mountpoint=/var/lib/docker/volumes/cannabia_pgdata/_data
```

### PASSO 2 — `docker run` com healthcheck

- Comando idiomático, credenciais via `--env-file` temporário (apagado imediatamente após o `docker run`)
- Healthcheck: `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB` a cada 5s
- **Tempo até `healthy`: 2 segundos**

### PAUSE 1 — validação de conexão (✅ APROVADA pelo humano)

```
docker ps: Up (healthy), 0.0.0.0:5434->5432/tcp
pg_isready: /var/run/postgresql:5432 - accepting connections
SELECT version(): retornou
```

Pequeno achado: `psql -c "\conninfo"` falha porque meta-commands não rodam em modo `-c`. Não impacta — `SELECT version()` provou a conexão.

### PASSO 3 — aplicar migrations 000→046

- Comando: `env\Scripts\python.exe -m src.infra.run_migrations`
- **46 migrations aplicadas em 11.5 segundos**
- Exit code 0
- Log completo em `migrations_run.log`

### PAUSE 2 — validação do schema (✅ APROVADA pelo humano)

| Query | Resultado |
|---|---|
| `COUNT(*) FROM schema_migrations` | **46** (001..046) |
| Min/Max versions | 001 / 046 |
| Gaps em 000..046 | apenas `000` (esperado — bootstrap) |
| Tabelas-chave (10 esperadas) | 10/10 presentes |
| Sprint 2 (044/045/046) timestamps | 22:29:45.x (sequencial, ~50ms entre cada) |
| Total tabelas em `public` | 97 |

### PASSO 4 — `seed_prompts.py --commit`

- Comando corrigido para `python -m scripts.seed_prompts --commit` (ver D-runtime-3)
- **7 inserted, 0 skipped, total 7** em 5.0 segundos

### PAUSE 3 — validação do prompt registry (✅ APROVADA pelo humano)

| Validação | Resultado |
|---|---|
| `COUNT(*) FROM ai_prompt_versions WHERE active = TRUE` | **7** |
| Versões | todas `v1.0.0`, `active=true`, `created_by=system_seed` |
| Tabela `prompt_registry` existe | NÃO (count = 0) — nome era do prompt original; tabela real é `ai_prompt_versions` |

Prompts semeados:
- anamnesis (hash `0e466960ebb1`)
- prescriber_system (`910a8c020e83`)
- prescriber_user (`d6cac1909b16`)
- scientific_report (`e7ca456c8f1d`)
- scientific_report_rag (`9209a214f89b`)
- treatment_plan (`001e1c2ea64e`)
- triage_agent (`e7298402082f`)

### PASSO 5 — subir backend Flask

- Comando: `python -m flask --app src.app run --port 5000 --host 127.0.0.1 --no-reload`
- Rodando em background, log em `backend.log`
- TCP listening em 127.0.0.1:5000 em ~5 segundos
- Warning esperado: `ENCRYPTION_KEY não definida. Derivando chave de SECRET_KEY via HKDF.` (comportamento dev)

### PASSO 6 — smoke test endpoints Tier-1

| Endpoint | HTTP | Tempo | Avaliação |
|---|---|---|---|
| `/api/v1/health` | **200** | 8.3s | ✅ chromadb=ok / circuit_breakers=closed / db=ok / gemini=ok / openai=ok / status=healthy. Lento porque chama APIs externas reais. |
| `/api/v1/appointments` | **401** | <1s | ✅ Auth gate, não 5xx |
| `/api/v1/attendances` | **401** | <1s | ✅ Auth gate, não 5xx |
| `/api/v1/conversations` | **401** | <1s | ✅ Auth gate, não 5xx |
| `/api/v1/anamnesis-reports` | 404 | — | Endpoint não existe (ver D-runtime-4) |

Critério "200 ou 401, nunca 5xx" atingido para todos os endpoints **que existem**. O 4º endpoint Tier-1 do prompt original era uma premissa equivocada.

### PASSO 7 — pg_dump com validação tripla

| Validação | Esperado | Obtido |
|---|---|---|
| V1 — `Length > 0` | > 0 | **408.382 bytes** ✅ |
| V2 — `pg_restore --list \| Measure-Object -Line` | > 5 linhas | **1041 linhas** ✅ |
| V3 — SHA-256 calculado | não-vazio | `59F15637247F6130E5D35A87C99F26633D854B46D25F7F29B3FF734DD264AD43` ✅ |

Registrado em `backups/postgres/CHECKSUMS.txt`. Arquivo gerado dentro do container e copiado via `docker cp` (evita corrupção de binário pelo PowerShell pipe). `/tmp/<dump>` removido do container após cópia.

**Esta validação tripla é exatamente o controle que faltava nos dumps `cannabia_pre_scc_I1_.*` zerados** (BUG-001).

---

## ACHADOS D-runtime (divergências entre prompt e realidade)

### D-runtime-1: Critério de sucesso ajustado (47 → 46)

**Contexto:** Prompt GO EXECUÇÃO especificava `COUNT(*) FROM schema_migrations = 47`.

**Realidade:** 46 registros (001..046), sem gaps. O arquivo `000_migration_tracking.sql` cria a própria tabela de tracking via bootstrap `_ensure_tracking_table()` no runner ([src/infra/run_migrations.py:88](src/infra/run_migrations.py#L88)) e por isso não se auto-registra. Comportamento padrão de sistemas de migração (cf. `alembic_version`).

**Origem da divergência:** premissa no prompt contou 47 arquivos como se todos fossem registráveis. Erro de especificação, não de execução.

**Ação:** critério atualizado para 46. Sem mudança no código nem no runner.

### D-runtime-2: Nome de tabela ajustado (`prompt_registry` → `ai_prompt_versions`)

**Contexto:** Prompt GO EXECUÇÃO pedia `SELECT COUNT(*) FROM prompt_registry = 7`.

**Realidade:** Tabela real é `ai_prompt_versions` (criada na migration `001_initial_schema.sql` e estendida pela `046_prompt_registry_alignment.sql`). Tabela `prompt_registry` **não existe** no schema (confirmado por query a `information_schema.tables`).

**Origem:** referência informal ao módulo `src/ai/prompt_registry.py` (o registry-em-código), confundida com a tabela DB que ele consome.

**Ação:** validação aplicada como `COUNT(*) FROM ai_prompt_versions WHERE active = TRUE`. Resultado: 7.

### D-runtime-3: Comando do seed corrigido (`python scripts/...` → `python -m scripts.seed_prompts`)

**Contexto:** Prompt GO EXECUÇÃO especificava `python scripts/seed_prompts.py --commit`.

**Realidade:** Essa invocação falha com `ModuleNotFoundError: No module named 'src'` porque o script tem `from src.ai.prompt_registry import _HARDCODED_PROMPTS` e o root do projeto não está no PYTHONPATH quando o arquivo é executado diretamente.

**Solução documentada no próprio script** (`scripts/seed_prompts.py` linhas 10-13): usar `python -m scripts.seed_prompts --commit`. Quando rodado como módulo, o cwd entra no PYTHONPATH e o import resolve.

**Ação:** comando ajustado em runtime. Mesma flag `--commit`, mesmo resultado (7 inserted, 0 skipped).

### D-runtime-4: 4º endpoint Tier-1 não existe como rota separada

**Contexto:** Prompt previa "4 endpoints Tier-1 da Sprint 2". Discovery sugeriu `/api/v1/anamnesis-reports` como possível 4º.

**Realidade:** Sprint 2 Track Page Tier-1 produziu **3 endpoints públicos com paginação canônica** (`/appointments`, `/attendances`, `/conversations`) + extensão dos repositórios subjacentes (memórias S2865, S2867, S2869, S2872, S2874). O `anamnesis_repository.list_reports()` é consumido por `/api/v1/attendances` — não há rota dedicada `/anamnesis-reports`.

**Ação:** critério ajustado para "3 endpoints Tier-1 com paginação + saúde geral". Todos respondem 401 (auth gate). Saúde retorna 200 com todos componentes healthy.

---

## ESTADO FINAL DO AMBIENTE

### Docker
```
CONTAINER: cannabia-postgis
  IMAGE:    postgis/postgis:16-3.5-alpine
  STATUS:   Up (healthy)
  PORT:     0.0.0.0:5434->5432/tcp
  RESTART:  unless-stopped
  HEALTH:   pg_isready a cada 5s

VOLUME:    cannabia_pgdata  (driver=local, persistent)
```

### Banco de dados
- 97 tabelas em `public`
- `schema_migrations` com 46 registros (001..046, head = 046)
- `ai_prompt_versions` com 7 prompts ativos (`v1.0.0`)
- Migrations Sprint 2 LGPD (044, 045) e Reg (046) aplicadas com timestamps sequenciais

### Backend Flask
- Rodando em `http://127.0.0.1:5000`
- `/api/v1/health` retorna `{status: "healthy"}` com todos componentes ok
- 3 endpoints Tier-1 com auth gate funcionando

### Frontend
- **NÃO subido nesta reconstrução** (decisão Q4a do PHASE0)
- `frontend/node_modules`, `.next`, `tsconfig.tsbuildinfo` preservados — basta `npm run dev` quando precisar

### Backup
- `backups/postgres/cannabia_post_rebuild_20260515_2023.dump` (408 KB, SHA-256 `59F1...AD43`)
- Validação tripla passou (Length, pg_restore --list = 1041, hash)

---

## CRITÉRIOS DE SUCESSO (revisados e atendidos)

- [x] Container `cannabia-postgis` healthy
- [x] `SELECT COUNT(*) FROM schema_migrations` = **46** (ajustado de 47 — D-runtime-1)
- [x] `SELECT COUNT(*) FROM ai_prompt_versions WHERE active=TRUE` = **7** (ajustado nome da tabela — D-runtime-2)
- [x] Endpoints Tier-1 da Sprint 2 respondendo (200 ou 401, nunca 5xx) — 3 confirmados + `/health` 200 (ajustado quantidade — D-runtime-4)
- [x] Backup validado em `backups/postgres/cannabia_post_rebuild_*.dump` (3 validações OK)
- [x] `backups/postgres/CHECKSUMS.txt` populado com SHA-256
- [x] `BUGS_DETECTED.md` criado com BUG-001
- [x] Dumps zerados movidos para `backups/postgres/incident_20260514_zero_dumps/`
- [x] `RELATORIO_DOCKER_RECON_EXEC.md` gerado (este documento)

---

## RESTRIÇÕES INVIOLÁVEIS — STATUS

- [x] **NÃO tocou produção (Render)** — zero chamadas remotas
- [x] **NÃO printou credenciais** — `.env` lido apenas em memória, parseado com `user_len/pwd_len` em vez de valores, `--env-file` temporário criado e removido na mesma transação
- [x] **Pause points respeitados** — PAUSE 1, 2, 3 aguardaram aprovação humana antes de avançar
- [x] **Não improvisou** — D-runtime-1 forçou pausa não programada; D-runtime-3 foi correção mínima documentada no próprio script
- [x] **Nada comitado** — repo limpo de PRs ou commits desta sessão
- [x] **Dumps zerados preservados** — movidos, não deletados (Ajuste B)
- [x] **Seed rodado com `--commit`** (Ajuste A)
- [x] **PASSO 7 só marcado OK após validação tripla** (Ajuste C)

---

## FOLLOW-UPS RECOMENDADOS

### F1 — Investigar BUG-001 (dumps zerados pré-incidente)
- **Por que:** o backup de 11/05 saiu com 0 bytes e ninguém percebeu até o incidente do dia 14. Esse é o **mesmo modo de falha** que a validação tripla deste PASSO 7 elimina — mas só pro futuro. Precisa entender se há job cron/scheduled task gerando dumps regulares e por que ele falhou silenciosamente.
- **Onde:** procurar `scripts/backup*`, Task Scheduler do Windows, ou jobs do Render.
- **Sprint candidata:** Sprint 3 Obs-Harden.

### F2 — Atualizar `.env.example` com vars runtime ausentes
- **Variáveis a adicionar** (encontradas via grep `os.getenv` em `src/` durante discovery):
  - `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_SAMPLE_RATE`, `SENTRY_TRACES_SAMPLE_RATE`
  - `FF_PROMPT_REGISTRY_ADMIN`
  - `CASE_AGGREGATE_MIN_K`, `LEGISLATION_DIR`
  - `ANCHOR_PROVIDER`, `NOTIFICATION_PROVIDER`, `POLYGON_RPC/KEY/ADDR/NETWORK`
- **PR separado**, não nesta reconstrução. Sprint 3 candidata.

### F3 — Esclarecer `LGPD_PURGE_KILL_SWITCH`
- **Achado do discovery:** variável **não existe** em `src/` nem em `.env.example`, embora o prompt original a mencionasse.
- **O controle real** está nos scripts `scripts/retention_audit_logs.py` e `scripts/purge_audit_pii_pre_a3.py` (flags CLI, não env var).
- **Ação:** documentar isso onde a Sprint 2 LGPD mencionou o "kill switch" — usuário pode estar referindo a outra variável. Não bloqueia nada.

### F4 — Adicionar `backups/` ao `.gitignore`
- **Por que:** dumps Postgres não devem ir pro git (binário, sensível, grande).
- **Por que não fiz agora:** restrição "não commitar nada durante a reconstrução" + para evitar diff a comitar.
- **Sugestão:** commit dedicado em PR de Sprint 3 com `.gitignore` + remover possíveis cópias antigas do índice.

### F5 — Documentar o setup Docker local em `docs/`
- **Lacuna:** `README.md` não menciona Docker. O setup do `cannabia-postgis` era conhecimento tácito.
- **Sugestão:** criar `docs/LOCAL_DEV.md` com o comando `docker run` (sem credenciais), o runner de migrations, e o `seed_prompts --commit`. Inclui o ritual de backup validado.

### F6 — Considerar adicionar healthcheck no `docker run` ao docs
- O healthcheck que adicionei (`pg_isready -U $POSTGRES_USER -d $POSTGRES_DB`) leva o container de "starting" a "healthy" em 2s e dá monitoramento contínuo. Vale documentar.

### F7 — Stop sair do `amigao_do_meio_ambiente-worker-1` em restart-loop
- Container de outro projeto observado durante o snapshot PASSO 0, estado "Restarting (1) X seconds ago".
- **NÃO toquei** — fora de escopo.
- **Sugestão:** avisar dono do projeto Amigão (provavelmente o mesmo desenvolvedor) para parar manualmente se incomodar.

---

## NOTAS FINAIS

- **A reconstrução foi mais simples do que o prompt original projetava.** O CannabIA ser Flask-no-host + 1 Postgres em Docker é, paradoxalmente, mais resiliente a incidentes de Docker do que stacks compose-heavy. Os outros projetos do mesmo `docker volume ls` (amigao, vereda, enjoyfun) teriam saído mais caros.

- **3 pause points humanos demonstraram valor real.** A pausa não-programada em PAUSE 2 (47→46) é o melhor exemplo: melhor 30 segundos de pausa do que aceitar um critério mal definido como falho.

- **Validação tripla do backup deve virar padrão.** O BUG-001 é caso de escola para esse controle. Vale incorporar essa rotina (Length + pg_restore --list + SHA-256 em CHECKSUMS.txt) em qualquer job de backup futuro do projeto.

- **Backend está em background nesta sessão.** Quando quiseres parar, basta um `taskkill /F /IM python.exe` ou descobrir o PID pelo log e finalizar.

🟢 Reconstrução verde. Próxima ação fica a teu critério.
