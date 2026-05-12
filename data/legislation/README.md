# Legislacao Regulatoria

Esta pasta tem um manifesto canonico em `sources.json` e um downloader em
`scripts/download_legislation_sources.ps1`.

## Seed inicial priorizado (Sprint 3)

- `RDC_327_2019_ANVISA.pdf` (binario, scrape BVS Saude)
- `RDC_660_2022_ANVISA.md` (HTML do DOU/Imprensa Nacional)
- `Lei_11_343_2006_Planalto.md` (HTML do Planalto/CCIVIL)
- `Resolucao_CFM_2113_2014.md` (HTML do portal CFM)

## Como baixar / atualizar

1. Execute `powershell -ExecutionPolicy Bypass -File scripts/download_legislation_sources.ps1`
2. (Sprint 3) Sanitize os markdowns HTML: `env/Scripts/python.exe scripts/sanitize_legislation_markdowns.py`
3. Revise os arquivos baixados em `data/legislation/`
4. Faca o upload para a Google Files API via uma destas opcoes:
   - HTTP: `POST /api/v1/regulatory/upload` (admin-only)
   - CLI: `env/Scripts/python.exe scripts/upload_legislation.py --commit`

## Sanitizacao de markdowns (Sprint 3 Leg.2)

Os HTMLs brutos do DOU/Planalto/CFM trazem boilerplate (nav, scripts,
analytics, accessibility widgets) que infla o consumo de tokens do Gemini
Files API. O script `scripts/sanitize_legislation_markdowns.py` gera
arquivos paralelos `*_sanitized.md` mantendo apenas o texto normativo.

Decisao operacional:
- Os originais (`*.md`) ficam preservados como base auditavel do scrape.
- Os `*_sanitized.md` ficam ao lado, prontos para upload otimizado.
- O manifesto `sources.json` declara o campo opcional `sanitized_filename`
  apontando para a versao limpa quando aplicavel.
- O uploader continua apontando para o `filename` original por padrao;
  futura iteracao pode alternar para `sanitized_filename` para reduzir
  tokens do Gemini (~68% de reducao medida em Sprint 3).

## Formatos aceitos pelo pipeline

- `.pdf`
- `.txt`
- `.md`
- `.docx`

## Schema do manifesto `sources.json`

Cada entrada suporta:

| Campo | Obrigatorio | Descricao |
|-------|-------------|-----------|
| `filename` | sim | Nome do arquivo na pasta `data/legislation/` |
| `title` | sim | Titulo curto da norma |
| `norm_number` | sim | Numero canonico (ex.: "RDC 660/2022") |
| `norm_body` | sim | Orgao emissor (ANVISA, CFM, Congresso Nacional...) |
| `source` | sim | Origem do scrape (anvisa, planalto, cfm, manual_upload) |
| `source_url` | recomendado | URL oficial |
| `download_mode` | sim | `binary` (PDF) ou `html` |
| `publication_date` | recomendado | ISO `YYYY-MM-DD` (Sprint 3) |
| `norm_status` | recomendado | `vigente` / `revogada` / `sustada` (Sprint 3) |
| `revoked_by` | opcional | Norma que revogou, se aplicavel (Sprint 3) |
| `sanitized_filename` | opcional | Nome do `*_sanitized.md` paralelo (Sprint 3) |
| `notes` | opcional | Observacoes editoriais |

## Observacao regulatoria

A trilha do CFM exige leitura cuidadosa: a `Resolucao CFM 2.324/2022` foi
publicada em 14/10/2022, mas seus efeitos foram sustados pela
`Resolucao CFM 2.326/2022` em 24/10/2022. Por isso o seed usa a
`Resolucao CFM 2.113/2014` como documento minimo. O campo `norm_status`
em `sources.json` permite registrar essa situacao.
