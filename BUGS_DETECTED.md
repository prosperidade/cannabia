# Bugs Detectados — Discovery Pós-Incidente 14/05/2026

## BUG-001: Dumps de backup com 0 bytes

- **Arquivos**: `cannabia_pre_scc_I1_.d`, `cannabia_pre_scc_I1_.dump` (2 arquivos)
- **Tamanho**: 0 bytes cada
- **Data de criação**: 2026-05-11 21:58 (3 dias antes do incidente Docker do dia 14/05)
- **Localização original**: raiz do projeto (`c:\Users\Administrador\Desktop\Cannabia\`)
- **Movidos para**: `backups/postgres/incident_20260514_zero_dumps/`
- **Detectados em**: 2026-05-15 durante reconstrução pós-incidente Docker (RELATORIO_DOCKER_RECON.md)

### Hipóteses

1. `pg_dump` executado contra container parado ou inacessível
2. Falha de autenticação silenciosa (`pg_dump` retorna 0 e cria arquivo vazio em alguns cenários de erro)
3. Disco cheio no momento do dump (confirmado pelo histórico: motivou o `docker prune` do dia 14/05)
4. Script de backup com erro não tratado (redirect `> arquivo.dump` cria arquivo vazio se o comando falhar)
5. Tentativa de backup pré-Sprint SCC-I1 (nome sugere "pre_scc_I1") interrompida

### Impacto

- **Ausência de backup utilizável no incidente de 14/05/2026**: quando `docker volume prune -f` apagou o volume do `cannabia-postgis`, não havia restore point.
- Risco recorrente: se o processo de backup atual nunca foi validado, qualquer próximo incidente terá o mesmo desfecho.

### Investigação

- **Pendente** — candidata a Sprint 3 (Obs-Harden) ou follow-up dedicado.
- Itens a apurar:
  - Onde está o script/cron que gerou esses dumps (procurar `scripts/backup*`, `tasks/backup*`, scheduled tasks do Windows)
  - Por que `pg_dump` retornou sucesso (?) deixando arquivo vazio
  - Se há logs do `pg_dump` no momento da execução
  - Se a `DATABASE_URL` daquele momento apontava para o container correto

### Severidade

**ALTA** — backup é controle crítico de continuidade. A ausência foi materializada no incidente real do dia 14/05.

### Mitigação imediata aplicada (2026-05-15)

A reconstrução pós-incidente (PASSO 7 do plano executor) inclui **validação tripla** do `pg_dump` recém-criado:

1. `(Get-Item arquivo.dump).Length -gt 0`
2. `pg_restore --list arquivo.dump | Measure-Object -Line` > 5 linhas
3. SHA-256 registrado em `backups/postgres/CHECKSUMS.txt`

Essa rotina deve virar padrão em todo job de backup futuro.
