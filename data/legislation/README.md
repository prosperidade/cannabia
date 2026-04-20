# Legislacao Regulatoria

Esta pasta passou a ter um manifesto canônico em `sources.json` e um downloader em
`scripts/download_legislation_sources.ps1`.

## Seed inicial priorizado

- `RDC_327_2019_ANVISA.pdf`
- `RDC_660_2022_ANVISA.md`
- `Lei_11_343_2006_Planalto.md`
- `Resolucao_CFM_2113_2014.md`

## Como baixar

1. Execute `powershell -ExecutionPolicy Bypass -File scripts/download_legislation_sources.ps1`
2. Revise os arquivos baixados em `data/legislation/`
3. Faça o upload para a Google Files API via `upload_all_legislation()`

## Formatos aceitos pelo pipeline

- `.pdf`
- `.txt`
- `.md`
- `.docx`

## Observacao regulatoria

A trilha do CFM precisa de leitura cuidadosa: a `Resolução CFM 2.324/2022` foi publicada
em 14/10/2022, mas seus efeitos foram sustados pela `Resolução CFM 2.326/2022` em
24/10/2022. Por isso, o seed inicial usa a base oficial da `Resolução CFM 2.113/2014`
como documento mínimo até consolidação documental posterior.
