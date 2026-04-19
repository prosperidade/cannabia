# Migrations — Rollback (down scripts)

## Propósito

Esta pasta guarda scripts **manuais** de reversão das migrations em `migrations/*.sql`.

O runner oficial (`src/infra/run_migrations.py`) só aplica migrations para frente (versionado por prefixo + checksum SHA-256). Rollback é uma operação deliberada, quase sempre emergencial, e exige decisão humana — portanto **não** é automatizada.

## Quando usar

- Regressão em produção causada por uma migration recém-aplicada e ainda não consolidada.
- Correção de dados durante uma janela de manutenção curta.
- Ambiente de staging/dev onde queremos voltar a um estado anterior antes de re-aplicar com o SQL corrigido.

**Nunca** execute um down script em produção sem:

1. Backup recente validado (ver `docs/BACKUP_AND_DISASTER_RECOVERY.md`).
2. Janela de manutenção anunciada (tráfego pode ficar inconsistente durante a reversão).
3. Leitura integral do arquivo down correspondente — algumas reversões têm efeito destrutivo documentado no cabeçalho do próprio script (ex.: `023_*_down.sql` descarta o fuso-horário).

## Política de cobertura

- **Obrigatório a partir da migration `022`**: toda nova migration `NNN_<tema>.sql` deve vir acompanhada de `migrations/down/NNN_<tema>_down.sql` no mesmo commit.
- **Retroativo**: migrations `001`–`021` não têm down scripts porque o histórico dessa base já foi estabilizado em produção e a reversão seletiva dessas mudanças exigiria mais análise de dados do que replay limpo de backup. O caminho oficial para voltar a um estado anterior a `022` é **restauração por backup**, não rollback DDL.

## Procedimento de rollback

Executar a partir do diretório raiz, com `DATABASE_URL` apontando para o banco a ser revertido:

```bash
# 1. Aplicar o down script (dentro de transação, se o SQL permitir)
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/down/NNN_<tema>_down.sql

# 2. Apagar o registro em schema_migrations — caso contrário o runner pula a re-aplicação
psql "$DATABASE_URL" -c "DELETE FROM schema_migrations WHERE version = 'NNN';"

# 3. (Opcional) validar o estado
psql "$DATABASE_URL" -c "SELECT version, filename FROM schema_migrations ORDER BY version;"
```

Após o rollback, a próxima execução de `python scripts/run_migrations.py` re-aplicará a migration `NNN` normalmente, usando o `.sql` de up atual na pasta `migrations/`.

## Convenções

- Nome do arquivo: `NNN_<mesmo_tema>_down.sql`.
- Cabeçalho obrigatório descrevendo o que é revertido, o que **não** é reversível e por quê.
- Idempotente sempre que possível (`DROP ... IF EXISTS`, `DROP CONSTRAINT IF EXISTS`, etc.).
- Sem `INSERT INTO schema_migrations` ou `DELETE FROM schema_migrations` dentro do SQL — isso é decisão do operador (passo 2 do procedimento acima).
- Converter dados de volta **explicitamente** quando a migration up fez transformação: o down precisa documentar se há perda informacional (ex.: TIMESTAMPTZ → TIMESTAMP perde fuso).

## Relacionado

- `docs/BACKUP_AND_DISASTER_RECOVERY.md` — política de backup/DR e quando usar restore em vez de rollback.
- `docs/runbook.md` — seção "Migrations" para o fluxo up.
- `docs/BACKLOG_SCC.md` (P0.5) — origem desta política.
