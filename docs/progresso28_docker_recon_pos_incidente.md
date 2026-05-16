# Progresso 28 — Reconstrucao Docker pos-incidente 14/05

**Data:** 2026-05-15
**Branch:** `feat/docker-recon-pos-incidente-20260514`
**Contexto:** rehidratacao do banco local apos `docker volume prune` ter apagado o volume do `cannabia-postgis` no incidente do dia 14/05
**Suite nesta sessao:** nao rodada; validado via smoke test dos 4 endpoints Tier-1 da Sprint 2 + `/api/v1/health`
**Producao (Render):** intocada. Zero chamadas remotas durante toda a sessao.

## 1. Objetivo desta entrada

Documentar a reconstrucao completa do ambiente Docker local apos o incidente de 14/05/2026, em que um `docker volume prune -f` (executado para liberar disco) apagou o volume nomeado do `cannabia-postgis`. A produzao no Render NAO foi afetada.

A reconstrucao foi conduzida em **3 fases** com metodologia Discovery -> Phase 0 -> Execucao com pause points, gerando 4 documentos de auditoria:

- [RELATORIO_DOCKER_RECON.md](../RELATORIO_DOCKER_RECON.md) — Fase 1 (Discovery)
- [PHASE0_DOCKER_RECON.md](../PHASE0_DOCKER_RECON.md) — Fase 2 (Phase 0, 4 blocos)
- [RELATORIO_DOCKER_RECON_EXEC.md](../RELATORIO_DOCKER_RECON_EXEC.md) — Fase 3 (Execucao)
- [BUGS_DETECTED.md](../BUGS_DETECTED.md) — BUG-001 (dumps zerados pre-incidente)

## 2. O que foi reconstruido

| Item | Estado final |
|---|---|
| Container | `cannabia-postgis` (`postgis/postgis:16-3.5-alpine`), porta 5434, `--restart unless-stopped`, healthcheck `pg_isready` 5s, status **healthy** |
| Volume | `cannabia_pgdata` nomeado, persistente, driver=local |
| Migrations | 46 aplicadas (001..046), head = 046, em 11.5s |
| Tabelas | 97 em schema `public` (10 tabelas-chave validadas) |
| Prompt registry | 7 prompts ativos em `ai_prompt_versions` (`v1.0.0`, `created_by=system_seed`) |
| Backend Flask | UP em `127.0.0.1:5000`, todos componentes healthy (chromadb, db, openai, gemini, circuit_breakers) |
| Backup pos-rebuild | 408 KB, SHA-256 `59F1...AD43`, registrado em `backups/postgres/CHECKSUMS.txt` |

## 3. Achados D-runtime (premissas do prompt vs realidade)

A metodologia com pause points expos 4 divergencias entre o prompt de execucao e a realidade do codigo. Todas foram discrepancias do prompt, nao erros de execucao.

| ID | Premissa do prompt | Realidade | Resolucao |
|---|---|---|---|
| D-runtime-1 | `COUNT(*) FROM schema_migrations = 47` | 46 (001..046). O arquivo `000_migration_tracking.sql` cria a propria tabela de tracking via bootstrap e por isso nao se auto-registra. Padrao alembic/flyway. | Criterio atualizado para 46. |
| D-runtime-2 | `SELECT COUNT(*) FROM prompt_registry = 7` | Tabela real e `ai_prompt_versions`. `prompt_registry` nao existe no schema. | Validacao aplicada como `WHERE active = TRUE`. Resultado: 7. |
| D-runtime-3 | `python scripts/seed_prompts.py --commit` | Falha com `ModuleNotFoundError: No module named 'src'`. Doc do proprio script (linhas 10-13) usa `python -m scripts.seed_prompts --commit`. | Comando corrigido em runtime. Mesma flag, mesmo resultado. |
| D-runtime-4 | "4 endpoints Tier-1 da Sprint 2" | Sprint 2 Track Page produziu **3 endpoints publicos** com paginacao (`/appointments`, `/attendances`, `/conversations`) + extensao dos repositorios. `anamnesis_repository.list_reports()` e consumido por `/api/v1/attendances`, sem rota dedicada `/anamnesis-reports`. | Criterio ajustado para 3 endpoints + `/health`. Todos passaram. |

A pausa **PAUSE 2** foi nao-programada — disparada por D-runtime-1 — e validou a metodologia: melhor parar 30 segundos do que aceitar criterio mal definido como falho.

## 4. Smoke test final

| Endpoint | HTTP | Tempo | Avaliacao |
|---|---|---|---|
| `/api/v1/health` | 200 | 8.3s | chromadb=ok, db=ok, circuit_breakers=closed, gemini=ok, openai=ok, status=**healthy**. Lento porque chama APIs externas reais. |
| `/api/v1/appointments` | 401 | <1s | Auth gate, nao 5xx |
| `/api/v1/attendances` | 401 | <1s | Auth gate, nao 5xx |
| `/api/v1/conversations` | 401 | <1s | Auth gate, nao 5xx |

Criterio "200 ou 401, nunca 5xx" atendido em todos os endpoints existentes.

## 5. Validacao tripla do backup (controle novo)

Os dois dumps `cannabia_pre_scc_I1_.*` (3 dias antes do incidente) tinham **0 bytes** — backup falhou silenciosamente, ninguem percebeu, e quando o `docker volume prune` rodou no dia 14 nao havia restore point.

Para evitar repetir o mesmo modo de falha, todo `pg_dump` pos-rebuild agora passa por **3 validacoes obrigatorias**:

1. `(Get-Item arquivo.dump).Length -gt 0` — arquivo nao vazio
2. `pg_restore --list arquivo | Measure-Object -Line > 5` — estrutura valida
3. SHA-256 calculado e registrado em `backups/postgres/CHECKSUMS.txt`

Os dumps zerados foram preservados como evidencia em `backups/postgres/incident_20260514_zero_dumps/` (Ajuste B do prompt de execucao). Nao foram deletados — sao a prova material do BUG-001.

## 6. Restricoes inviolaveis honradas

- [x] Producao (Render) intocada — zero chamadas
- [x] Credenciais nao printadas — `.env` lido em memoria, parseado com `user_len/pwd_len`, env-file temporario removido na mesma transacao
- [x] Pause points respeitados — PAUSE 1, 2 e 3 aguardaram aprovacao humana
- [x] Sem improviso — D-runtime-1 forcou parada nao programada; demais ajustes foram corrigir comandos com base em documentacao do proprio codigo
- [x] Nada comitado durante a execucao — commit so apos GO encerramento
- [x] Dumps zerados preservados (movidos, nao deletados)
- [x] Seed rodado com `--commit` explicito (Ajuste A)
- [x] PASSO 7 (backup) so marcado OK apos validacao tripla (Ajuste C)

## 7. Follow-ups que ficaram abertos

| ID | Acao | Sprint candidata |
|---|---|---|
| F1 | **Investigar BUG-001** — descobrir por que os dumps de 11/05 sairam zerados (cron quebrado? auth silenciosa? disco cheio?). Esse e o mais urgente. | Sprint 3 Obs-Harden |
| F2 | Atualizar `.env.example` com vars runtime ausentes: `SENTRY_DSN/ENVIRONMENT/SAMPLE_RATE`, `FF_PROMPT_REGISTRY_ADMIN`, `CASE_AGGREGATE_MIN_K`, `LEGISLATION_DIR`, `ANCHOR_PROVIDER`, `NOTIFICATION_PROVIDER`, `POLYGON_*` | Sprint 3 Obs-Harden |
| F3 | Esclarecer `LGPD_PURGE_KILL_SWITCH` — variavel **nao existe** em `src/` nem em `.env.example`. O controle real esta em flags CLI dos scripts `retention_audit_logs.py` e `purge_audit_pii_pre_a3.py`. Documentar onde a Sprint 2 LGPD mencionou. | Sprint 3 |
| F4 | `.gitignore` ja atualizado neste commit para excluir `backups/postgres/*.dump`, `*.d`, `.tmp/` e `incident_*/`. | Feito |
| F5 | Criar `docs/LOCAL_DEV.md` documentando o setup Docker local (comando `docker run` sem credenciais, runner de migrations, `seed_prompts --commit`, ritual de backup validado) | Proxima passada |
| F6 | Considerar formalizar healthcheck nos docs (`pg_isready -U $POSTGRES_USER -d $POSTGRES_DB` levou container a `healthy` em 2s) | Proxima passada |
| F7 | Container `amigao_do_meio_ambiente-worker-1` em restart-loop (de outro projeto) observado no snapshot — fora de escopo, **nao toquei**. Avisar o dono se incomodar. | Externo |

## 8. Reflexoes / aprendizados desta sessao

1. **A reconstrucao foi mais simples do que o prompt original projetava.** O CannabIA ser Flask-no-host + 1 Postgres em Docker e, paradoxalmente, mais resiliente a incidentes de Docker do que stacks compose-heavy. Os outros projetos do mesmo `docker volume ls` (amigao, vereda, enjoyfun) teriam saido mais caros.

2. **3 pause points humanos demonstraram valor real.** A pausa nao-programada em PAUSE 2 (47->46) e o melhor exemplo: melhor 30 segundos de pausa do que aceitar criterio mal definido.

3. **Validacao tripla do backup deve virar padrao.** O BUG-001 e caso de escola. Vale incorporar essa rotina (Length + pg_restore --list + SHA-256 em CHECKSUMS.txt) em qualquer job de backup futuro.

4. **Discovery valeu cada minuto.** Encontrou que nao existe `docker-compose.yml`, que `LGPD_PURGE_KILL_SWITCH` e nome fantasma, que dumps recentes estavam zerados, e que a tabela e `ai_prompt_versions` (nao `prompt_registry`). Esses 4 achados teriam virado falhas de execucao se a fase de discovery tivesse sido pulada.

## 9. Estado para a proxima passada

- Ambiente local pronto para Sprint 3 (SCC-I1, Legislacao-Real, CFD, Obs-Harden, Page-Migration).
- Backend Flask deixado rodando em background nesta sessao — pode ser parado a qualquer momento.
- Nenhum bloqueio identificado para retomar trabalho de codigo.
- F1 (investigar BUG-001) deve abrir a Sprint 3 Obs-Harden — backup que falha silenciosamente e maior risco do que qualquer feature pendente.
