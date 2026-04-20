# Progresso 9 — Validação Local + Higiene de Setup e Migrations

## Data
2026-04-15

## Objetivo do bloco
1. Instalar o ambiente de testes local
2. Rodar a suíte real e corrigir falhas concretas
3. Sanear o setup Python e o runner de migrations
4. Atualizar o backlog executivo para refletir o novo estado do sistema

## Trabalho realizado

### 1. Ambiente de testes local fechado

- `pytest`, `pytest-cov` e `responses` foram instalados no `venv` local (`env\`)
- `requirements.txt` foi regravado em UTF-8 para voltar a ser legível pelo `pip`
- `gunicorn` passou a usar marker de plataforma para não quebrar instalação local em Windows
- A instalação completa via `requirements-dev.txt` passou a funcionar

### 2. Correção de segurança validada por teste

- `src/ai/validators.py` deixou de manter regex própria divergente
- O validador de anamnese agora reutiliza `src/ai/guardrails.py`
- O guardrail central foi ampliado para bloquear `ignore all previous instructions`
- Resultado: os testes de prompt injection voltaram a passar

### 3. Higiene de migrations

- `src/infra/run_migrations.py` passou a detectar conflito de versões duplicadas antes de aplicar migrations
- `scripts/run_migrations.py` foi reduzido a wrapper do runner versionado, eliminando a lógica paralela antiga
- Foram adicionados testes cobrindo:
  - ordenação canônica ignorando `000_migration_tracking.sql`
  - falha explícita em caso de versões duplicadas

### 4. Suíte verde

- Total validado localmente: `36` testes passando
- `python -m py_compile` executado com sucesso nos arquivos Python alterados

### 5. Cobertura inicial de admin agents

- Criado `tests/test_admin_agents.py`
- Cobertas as rotas:
  - listagem de agentes
  - inspeção de skills
  - execução administrativa de agente com CSRF
- Os testes foram isolados em uma app Flask mínima para não depender de banco/tenancy

## Validações executadas

- `env\Scripts\python.exe -m pip install pytest pytest-cov responses`
- `env\Scripts\python.exe -m pip install -r requirements-dev.txt`
- `env\Scripts\python.exe -m pytest -q`
- `env\Scripts\python.exe -m py_compile src\ai\guardrails.py src\ai\validators.py src\infra\run_migrations.py scripts\run_migrations.py tests\test_migrations.py`

## Estado executivo após este bloco

### Fechado

- base mínima de validação local
- regressão conhecida de prompt injection
- manifest Python quebrado por encoding
- alinhamento do script legado de migrations com o runner versionado

### Ainda aberto

- limpeza definitiva da trilha histórica de migrations renomeadas no branch/repositório
- validação real de `setup_local.py` com banco e seeds completos
- população de `data/legislation/` com documentos regulatórios reais
- cobertura de `/knowledge` e `/regulatory`
- aprofundamento da cobertura de `/admin/agents`

## Próximas missões recomendadas

1. Fechar a trilha canônica de migrations antigas vs renomeadas e validar `setup_local.py`
2. Popular a base regulatória real e validar o fluxo regulatory ponta a ponta
3. Expandir cobertura de testes para knowledge e regulatory, e aprofundar admin agents

## Arquivos relevantes do bloco

### Criado

- `docs/progresso9_validation_setup_hygiene.md`
- `tests/test_admin_agents.py`
- `tests/test_migrations.py`
- `tests/fixtures/migrations/canonical/*`
- `tests/fixtures/migrations/duplicate_versions/*`

### Modificados

- `requirements.txt`
- `.gitignore`
- `pytest.ini`
- `src/ai/guardrails.py`
- `src/ai/validators.py`
- `src/infra/run_migrations.py`
- `scripts/run_migrations.py`
- `docs/13_MASTER_DOCUMENT_INDEX.md`
- `docs/18_SPRINT_2_BACKLOG.md`
- `docs/21_AGENT_ARCHITECTURE.md`
- `docs/22_EXECUTIVE_BACKLOG.md`
