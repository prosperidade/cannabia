# Progresso 11 — Seed Regulatório Real + Upload para Google Files

## Data
2026-04-16

## Objetivo do bloco
1. Popular `data/legislation/` com documentos regulatórios oficiais
2. Ligar o upload regulatório ao `knowledge_catalog`
3. Validar a superfície `knowledge/regulatory` com testes
4. Fechar o seed inicial sem incluir artefatos auxiliares no fluxo

## Trabalho realizado

### 1. Seed regulatório canônico

- criado `data/legislation/sources.json` como manifesto oficial de fontes
- criado `scripts/download_legislation_sources.ps1` para baixar os documentos
- baixados para `data/legislation/`:
  - `RDC_327_2019_ANVISA.pdf`
  - `RDC_660_2022_ANVISA.md`
  - `Lei_11_343_2006_Planalto.md`
  - `Resolucao_CFM_2113_2014.md`

### 2. Persistência no catálogo

- criado `src/knowledge/legislation_catalog.py`
- `POST /api/v1/regulatory/upload` passou a sincronizar o `knowledge_catalog`
- o sync passou a:
  - preferir metadados canônicos do manifesto
  - reutilizar registros existentes por `source_url`, `norm_number/source` e `title/source`
  - fazer update em vez de abrir trilhas paralelas desnecessárias

### 3. Higiene do pipeline Google Files

- `src/knowledge/google_files.py` passou a respeitar `sources.json`
- `README.md` e outros artefatos auxiliares deixaram de ser tratados como legislação
- `mime_type` correto passou a ser persistido para `.pdf`, `.md`, `.txt` e `.docx`
- `list_uploaded_files()` e as queries agora operam somente sobre os arquivos canônicos

### 4. Carga real executada

- upload real executado para Google Files API
- catálogo local `data/file_catalog.json` ficou com `4` documentos canônicos
- `knowledge_catalog` ficou com `4` normas indexadas:
  - `RDC nº 327/2019`
  - `RDC nº 660/2022`
  - `Lei nº 11.343/2006`
  - `Resolução CFM nº 2.113/2014`
- duplicatas e artefato indevido (`README`) foram removidos do banco

### 5. Cobertura de testes

- criados:
  - `tests/test_google_files.py`
  - `tests/test_knowledge_routes.py`
  - `tests/test_regulatory_routes.py`
  - `tests/test_legislation_catalog.py`
- suíte local final: `49` testes passando

## Validações executadas

- `env\Scripts\python.exe -m pytest -q`
- `env\Scripts\python.exe -m py_compile src\knowledge\google_files.py src\knowledge\legislation_catalog.py`
- upload real via `upload_all_legislation()`
- sincronização real via `sync_legislation_catalog()`
- consulta direta no banco confirmando `4` documentos regulatórios `indexed`

## Bloqueio encontrado

- a consulta regulatória real com `query_legislation_structured()` falhou por quota da Gemini API:
  - `429 RESOURCE_EXHAUSTED`
  - modelo default observado: `gemini-2.0-flash`
- ou seja: a carga documental e o catálogo ficaram prontos, mas a validação final de geração ficou bloqueada por quota externa

## Próxima missão recomendada

1. Ajustar quota/plano/modelo da Gemini API para destravar `generate_content`
2. Rodar uma consulta regulatória real ponta a ponta
3. Atualizar backlog executivo e inventário para refletir que C1/C2 foram fechadas tecnicamente, com bloqueio residual apenas em quota de inferência
