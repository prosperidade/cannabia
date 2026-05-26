# Local Dev

## Setup

```bash
python scripts/setup_local.py
```

O script aplica migrations, seeds de usuarios e dados demo. Usuarios principais:

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
