# Local Dev

## Setup

Sequência de onboarding (rode **nesta ordem**, antes do primeiro `pytest`):

**1. Banco de dev** (migrations + seeds de usuários + dados demo):

```bash
python scripts/setup_local.py
```

**2. Banco de teste ISOLADO desta worktree** (obrigatório — sem ele, `pytest`
roda no banco de dev compartilhado e contamina outras worktrees/agentes):

```bash
python scripts/setup_worktree_db.py
# cole o TEST_DATABASE_URL impresso no .env DESTA worktree
```

> Todo agente/worktree novo precisa do passo 2 antes do primeiro `pytest`.
> Detalhes e troubleshooting em [Testes › Banco de teste isolado](#banco-de-teste-isolado-por-worktree-obrigatório-com-agentesworktrees-paralelos).

Usuarios principais (criados pelo passo 1):

| Login | Senha | Papel |
|---|---|---|
| `admin` | `admin123` | plataforma |
| `medico` | `medico123` | medico comum |
| `dono` | `dono123` | medico + dono da clinica |
| `recepcao` | `recepcao123` | operacao/recepcao |
| `financeiro` | `financeiro123` | financeiro |
| `admin_clinica` | `adminclinica123` | gestor local |
| `paciente` | `paciente123` | portal paciente |

## Rodar

Backend:

```bash
python -m src.app
```

Frontend:

```bash
cd frontend
npm run dev
```

Typecheck frontend:

```bash
cd frontend
npx tsc --noEmit
```

## Testes

Suite default, sem rede externa:

```bash
python -m pytest -q
```

### Banco de teste isolado por worktree (obrigatório com agentes/worktrees paralelos)

O `.env` aponta `DATABASE_URL` para o banco de **dev**, que também é usado pelos
testes. Se duas worktrees (ou dois agentes) rodarem `pytest` ao mesmo tempo
contra o **mesmo** banco, há contaminação cross-process — flakes intermitentes
(ex.: `test_smoke_full_pipeline` em jun/2026).

Cada worktree deve ter seu próprio banco de teste:

```bash
python scripts/setup_worktree_db.py        # cria cannabia_test_<hash> + migra
# cole o TEST_DATABASE_URL impresso no .env DESTA worktree
python scripts/setup_worktree_db.py --recreate   # recria do zero quando precisar
```

O `conftest.py` dá **precedência ao `TEST_DATABASE_URL`** sobre o `DATABASE_URL`
de dev. Sem ele, a suite emite um aviso alto antes de rodar no banco
compartilhado. A ordem dos testes é aleatorizada (`pytest-randomly`) para revelar
acoplamento; reproduza uma ordem com `--randomly-seed=<N>` ou desligue com
`-p no:randomly`. Valide isolamento rodando a suite em **duas seeds diferentes**.

O smoke real do Gemini so deve rodar quando for intencional validar provedor,
quota e arquivos reais:

```bash
set RUN_REAL_GEMINI_SMOKE=1
python -m pytest tests/test_regulatory_routes.py -q
```

## Backup Validado

Antes de manutencao sensivel e no export logico mensal:

```bash
python scripts/backup_postgres_validated.py
```

O script usa `DATABASE_URL`, gera `backups/postgres/<database>_<timestamp>.dump`
e valida:

- tamanho maior que zero
- `pg_restore --list`
- SHA-256 registrado em `backups/postgres/CHECKSUMS.txt`

Se `pg_dump` e `pg_restore` nao estiverem no `PATH`, configure `PG_BIN` no
`.env` ou passe `--pg-bin`.

Validar dump existente:

```bash
python scripts/backup_postgres_validated.py --validate-only backups/postgres/<arquivo>.dump
```
