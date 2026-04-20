# Progresso 10 — Tracking Canônico de Migrations + Documentação de Banco

## Data
2026-04-15

## Objetivo do bloco
1. Fechar a trilha canônica de migrations renomeadas
2. Validar `setup_local.py` com banco e seeds reais
3. Atualizar a documentação de migrations e banco ao estado real do repositório

## Trabalho realizado

### 1. Normalização do tracking de migrations

- `src/infra/run_migrations.py` passou a carregar `filename` + `checksum` do `schema_migrations`
- O runner agora:
  - falha cedo em caso de versões duplicadas
  - normaliza registros legados sem checksum
  - atualiza `filename` canônico quando o conteúdo da migration confere
- `_record_migration()` virou upsert real, permitindo corrigir rows antigas sem intervenção manual

### 2. Limpeza da sequência canônica `012`–`017`

- Foram removidos os `INSERT INTO schema_migrations ... checksum=''` embutidos nas SQLs:
  - `012_prescriptions_orders.sql`
  - `013_telemetry_timeseries.sql`
  - `014_missing_tables_and_columns.sql`
  - `015_users_enhancement.sql`
  - `016_knowledge_catalog.sql`
  - `017_knowledge_monitors.sql`
- Com isso, a responsabilidade de tracking fica exclusivamente no runner versionado

### 3. Cobertura de testes ampliada

- `tests/test_migrations.py` ganhou cenários para:
  - normalização de checksum legado vazio
  - normalização de `filename` legado quando o checksum bate
- Os testes foram ajustados para usar fixtures locais do repositório, evitando dependência do diretório temporário global do Windows

### 4. Validação operacional real

- `env\Scripts\python.exe scripts/setup_local.py` foi executado com sucesso contra PostgreSQL local
- Após a execução, `schema_migrations` ficou com checksum preenchido para `012` até `017`
- Os warnings falsos de checksum vazio deixaram de aparecer

### 5. Documentação atualizada

- `docs/08_DATABASE_AND_DOMAIN_MODEL.md`
  - expandido com o snapshot real do banco até as migrations `017`
  - adicionada seção explícita de governança de migrations
- `docs/16_CURRENT_SYSTEM_INVENTORY.md`
  - inventário de tabelas ampliado para refletir billing, prescriptions, telemetry, knowledge catalog e monitors
  - estado do runner e do setup local atualizado
- `docs/runbook.md`
  - comportamento do runner atualizado
  - `setup_local.py` marcado como validado
  - lista de migrations atualizada até `017`
- `docs/22_EXECUTIVE_BACKLOG.md`
  - F1/F2 marcados como concluídos
  - ordem das próximas missões reorganizada

## Validações executadas

- `env\Scripts\python.exe -m pytest -q tests\test_migrations.py`
- `env\Scripts\python.exe -m pytest -q`
- `env\Scripts\python.exe scripts\setup_local.py`
- consulta direta em `schema_migrations` confirmando checksums preenchidos em `012`–`017`

## Estado executivo após este bloco

### Fechado

- trilha canônica das migrations renomeadas
- normalização automática de tracking legado
- validação real de `setup_local.py`
- documentação principal de migrations e banco alinhada ao estado do repositório

### Ainda aberto

- população de `data/legislation/` com documentos regulatórios reais
- cobertura de `/knowledge` e `/regulatory`
- enriquecimento dos seeds para knowledge/regulatory
- contrato clínico mínimo para entrada segura do `AgentePrescritor`

## Próximas missões recomendadas

1. Popular a base regulatória real e validar o fluxo regulatory ponta a ponta
2. Expandir cobertura de `/knowledge`, `/regulatory` e smoke tests operacionais
3. Definir contrato de entrada estruturada para prescrição segura

## Arquivos relevantes do bloco

### Criado

- `docs/progresso10_migration_tracking_database_docs.md`

### Modificados

- `src/infra/run_migrations.py`
- `tests/test_migrations.py`
- `migrations/012_prescriptions_orders.sql`
- `migrations/013_telemetry_timeseries.sql`
- `migrations/014_missing_tables_and_columns.sql`
- `migrations/015_users_enhancement.sql`
- `migrations/016_knowledge_catalog.sql`
- `migrations/017_knowledge_monitors.sql`
- `docs/08_DATABASE_AND_DOMAIN_MODEL.md`
- `docs/16_CURRENT_SYSTEM_INVENTORY.md`
- `docs/runbook.md`
- `docs/22_EXECUTIVE_BACKLOG.md`
