# RCA — BUG-001: dumps de backup com 0 bytes (silenciosos)

- **Data do RCA:** 2026-06-11
- **Autor:** Track C (Onda 1, doc 30) — OBS-1
- **Severidade:** ALTA (controle crítico de continuidade)
- **Status:** **Causa-raiz fechada + controle automático instituído.**
- **Origem:** `BUGS_DETECTED.md`, `docs/progresso28_docker_recon_pos_incidente.md`, `MEMORY.md` (BUG-001), `docs/29.5_MERGULHO_SCC.md` §A8/R12, `docs/30` OBS-1.

## 1. Resumo

Em **2026-05-11 21:58**, dois dumps (`cannabia_pre_scc_I1_.d` e `cannabia_pre_scc_I1_.dump`) foram gerados na raiz do projeto com **0 bytes cada**. A falha foi **silenciosa** — ninguém percebeu. Em **2026-05-14**, um `docker volume prune -f` (executado para liberar disco) apagou o volume `cannabia_pgdata` do `cannabia-postgis`. **Não havia restore point utilizável.** A produção (Render) não foi afetada; o impacto foi no ambiente de desenvolvimento local, mas o modo de falha é o mesmo que comprometeria a produção.

## 2. Timeline

| Quando | Evento |
|---|---|
| 2026-05-11 21:58 | Backup ad-hoc pré-Sprint SCC-I1 gera 2 dumps de 0 bytes. Exit code não verificado; arquivos aceitos como válidos. |
| 2026-05-14 | Pressão de disco → `docker volume prune -f` apaga o volume do Postgres local. |
| 2026-05-15 | Reconstrução pós-incidente detecta os dumps zerados; institui validação tripla **manual** no ritual de backup (progresso28). Dumps zerados preservados como evidência em `backups/postgres/incident_20260514_zero_dumps/`. |
| 2026-06-11 | Este RCA: causa-raiz fechada + verificação tripla **automática** com heartbeat e alerta (Track C / OBS-1). |

## 3. Causa-raiz

O backup de 11/05 foi uma invocação **manual/ad-hoc** de `pg_dump` (o script validado `scripts/backup_postgres_validated.py` ainda não existia — foi criado em 15/05+). Pela evidência, a causa-raiz é a combinação:

1. **Escrita do arquivo desacoplada do sucesso do `pg_dump`.** O nome `cannabia_pre_scc_I1_.d`/`.dump` (note o `_` antes da extensão, sugerindo uma variável de timestamp vazia) e a existência de dois arquivos parciais (`.d` = formato directory, `.dump` = custom) são típicos de invocação manual com **redirecionamento de shell** (`pg_dump … > arquivo.dump`). Em PowerShell/CMD, o `>` **cria o arquivo vazio antes** de o `pg_dump` rodar; se o `pg_dump` falha, o arquivo vazio permanece.
2. **Exit code não verificado.** Sem checar `$LASTEXITCODE`/`returncode`, um `pg_dump` que falhou foi tratado como sucesso — a fonte da **silenciosidade**.
3. **Gatilho da falha do `pg_dump`:** o mais provável é **disco cheio** (corroborado: a pressão de disco motivou o `docker volume prune` de 14/05). Hipóteses alternativas plausíveis e não excludentes: container parado/inacessível, ou falha de autenticação silenciosa. Qualquer um destes, somado a (1)+(2), produz exatamente o sintoma observado.

> **Conclusão:** a causa-raiz não é um único trigger exótico, e sim a **ausência de verificação do resultado do backup** — um `pg_dump` mal-sucedido produziu um arquivo vazio que foi aceito sem checagem. O trigger imediato (disco cheio) é secundário ao controle ausente.

Não foi necessário acesso a infra indisponível para fechar o diagnóstico: a evidência material (arquivos preservados, nomes, datas, correlação com a pressão de disco de 14/05) é suficiente e converge.

## 4. Correção

### 4.1. Já em vigor (desde 15/05)
`scripts/backup_postgres_validated.py` **elimina o modo de falha na raiz**:
- usa `pg_dump --format=custom -f <arquivo>` (**sem** redirecionamento de shell);
- **verifica `returncode`** e remove o arquivo de 0 bytes em falha, levantando exceção;
- valida **tamanho > limiar** e **`pg_restore --list`**, e registra **SHA-256** em `CHECKSUMS.txt`.

### 4.2. Novo nesta remediação (OBS-1)
1. **3º gate — restauração de amostra:** `sample_restore_check()` roda `pg_restore --schema-only`, exercendo a descompressão de **todo o corpo** do arquivo (não só o TOC do `--list`). Pega dumps truncados/corrompidos que passariam no `--list`.
2. **Verificação automática + heartbeat:** `scripts/backup_verify.py` (cron `cannabia-backup-verify`) cria o dump, roda os 3 gates e **grava cada execução** (sucesso **ou** falha) em `backup_verification_events` (migration 053). Falha silenciosa vira falha **visível**.
3. **Alerta em falha:** em qualquer gate que falhe, `_alert()` dispara Sentry (se `SENTRY_DSN`) + log `ERROR`, e o processo sai com código ≠ 0.
4. **Heartbeat monitorável:** ausência de linha `success=TRUE` recente em `backup_verification_events` é um sinal de alerta de heartbeat (doc 30 §5).

## 5. Runbook de ativação (produção/Render)

> Itens que dependem de infra do Render — executar quando da liberação operacional. O cron já está no `render.yaml`, **kill-switched**.

1. Confirmar que `pg_dump`/`pg_restore` existem no ambiente do Render Cron Job (mesma major version do Postgres gerenciado). Se ausentes, adicionar ao `buildCommand` ou usar imagem com client tools.
2. Definir `SENTRY_DSN` no serviço `cannabia-backup-verify`.
3. Definir storage off-site para os dumps (ponto em aberto do `BACKUP_AND_DISASTER_RECOVERY.md` §7) — sem off-site, a verificação prova integridade mas não sobrevive à perda do host.
4. Virar `BACKUP_VERIFY_ENABLED=true` no dashboard.
5. Configurar um monitor de heartbeat: alertar se `MAX(started_at)` de `backup_verification_events WHERE success` for mais antigo que ~26h.
6. Validar a primeira execução: `SELECT * FROM backup_verification_events ORDER BY started_at DESC LIMIT 1`.

## 6. Lições

- **Backup sem verificação de resultado não é backup.** O custo do controle (3 checagens + 1 INSERT) é desprezível ante o custo materializado em 14/05.
- **Silêncio é o pior modo de falha.** O heartbeat existe para que a próxima falha de backup seja barulhenta.
- A validação tripla manual de 15/05 era a mitigação certa; esta remediação só a tornou **automática e auditável**.
