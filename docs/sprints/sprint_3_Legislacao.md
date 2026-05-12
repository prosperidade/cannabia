# Sprint 3 — Track Legislacao Real (hardening da base regulatoria)

**Base:** `main @ e2f9c39` (Sprint 2 consolidado). **Branch:** `feat/sprint-3-Legislacao-hardening`.
**Sub-agente:** Track Legislacao-Real (worktree `agent-a5bca0e4193ebc032`).
**Status:** Pronto para PR. **Frente coberta:** C1 + C2 do `22_EXECUTIVE_BACKLOG.md`.

## TL;DR

A Phase 0 desta track descobriu que a base regulatoria ja estava
substancialmente implementada antes da Sprint 3 (4 normas core seedadas em
`data/legislation/`, uploader Gemini Files API robusto com cache SHA-256, sync
com `knowledge_catalog`, endpoint `POST /api/v1/regulatory/query` real com
Gemini 2.0 Flash). O trabalho da Sprint 3 vira entao hardening + validacao
+ ergonomia operacional, fechando definitivamente C1 e C2 da Frente C.

| Bloco | Entregavel | Status |
|---|---|---|
| Leg.1 | Inventario gap (4 normas core batem com `sources.json` + arquivos no disco + SHA-256 do `data/file_catalog.json` em ambiente principal) | OK |
| Leg.2 | Sanitizacao de markdowns HTML (RDC 660, Lei 11.343, CFM 2.113). Reducao **68.1%** dos bytes -- 367.136 -> 117.264 bytes | OK |
| Leg.3 | `scripts/upload_legislation.py` -- CLI Python dry-run/commit, single-file, idempotente | OK |
| Leg.4 | `tests/fixtures/regulatory_queries.json` + 3 testes novos em `tests/test_regulatory_routes.py` (fixture + mock Gemini + smoke real condicional) | OK |
| Leg.5 | `sources.json` ganhou `norm_status`, `revoked_by`, `publication_date`, `sanitized_filename` | OK |
| Leg.6 | `legislation_catalog.infer_metadata` agora propaga `norm_status` do manifesto para o `knowledge_catalog` | OK |
| Leg.7 | Este documento + atualizacao da `README.md` em `data/legislation/` | OK |
| Leg.8 | `22_EXECUTIVE_BACKLOG.md` Frente C: C1 + C2 marcados como resolvidos Sprint 3 | OK |

## Decisoes do coordenador honradas

- **Q-Leg-1** -- `GOOGLE_API_KEY` configurada em dev (confirmado). Smoke real **quebrou no
  Gemini Files API com HTTP 429 RESOURCE_EXHAUSTED** (free tier daily limit zero -- quota
  ja consumida em sessoes anteriores). Conforme a politica acordada (`REPORTE e pule
  Leg.4`), mantemos Leg.4 implementado via mock, mas o `pytest.skipif`
  do smoke real esta presente para quando a quota voltar (`test_query_legislation_real_gemini_smoke`).
- **Q-Leg-2** -- 4 normas seed seguem cobrindo o piloto Sprint 3. Sem expansao de catalogo.
- **Q-Leg-3** -- Versionamento via `norm_status`/`revoked_by` no `sources.json` -- implementado.
- **Q-Leg-4** -- `scripts/upload_legislation.py` criado mantendo o endpoint HTTP.
- **Q-Leg-5** -- Fixture com **8 Q&A canonicas** (acima do minimo 6 sugerido).
- **Q-Leg-6** -- Custo Gemini esperado ~$0.20/dia no piloto. Observacao real ficou bloqueada por quota free-tier; assim que migrarmos para tier pago, capturar via `usage.total_tokens` ja retornado por `query_legislation`.
- **Q-Leg-7** -- Markdown HTML sanitizado. Reducao **medida** de 68.1% dos bytes -- significativamente acima da estimativa inicial de 40% no briefing.
- **Q-Leg-8** -- Roteamento por keyword permanece para Sprint 4.

## Detalhes operacionais

### Leg.1 -- Inventario gap

`data/legislation/sources.json` lista exatamente 4 entries, todas com arquivo presente no disco:

| Arquivo | Tamanho | Modo |
|---|---|---|
| `RDC_327_2019_ANVISA.pdf` | 0.22 MB | binary |
| `RDC_660_2022_ANVISA.md` | 0.09 MB | html |
| `Lei_11_343_2006_Planalto.md` | 0.25 MB | html |
| `Resolucao_CFM_2113_2014.md` | 0.01 MB | html |

`data/file_catalog.json` no ambiente principal (`c:\Users\Administrador\Desktop\Cannabia\data\file_catalog.json`) ja tem os 4 arquivos uploaded para o Gemini Files API com checksums SHA-256 batendo. O catalog **nao** e' commitado no repo (per-environment) -- mantemos no `.gitignore` implicito do worktree.

### Leg.2 -- Sanitizacao

Estrategia: produzimos arquivos paralelos `*_sanitized.md` mantendo o original como base auditavel do scrape bruto. O script `scripts/sanitize_legislation_markdowns.py` aplica strip seletivo de HTML, scripts, comentarios e boilerplate (nav, footer, accessibility widgets) por norma.

```text
Total: 367,136 bytes -> 117,264 bytes (68.1% reducao)
RDC 660/2022: 88.2% reducao
Lei 11.343/2006: 59.9% reducao
CFM 2.113/2014: 79.5% reducao
```

O uploader continua apontando para o arquivo original por default; o campo `sanitized_filename` no manifesto fica disponivel para uma Sprint 4 reapontar o upload para a versao limpa (e cortar ~68% de tokens Gemini por consulta).

### Leg.3 -- CLI upload

`env\Scripts\python.exe scripts/upload_legislation.py --dry-run` lista o manifesto sem upload.

`env\Scripts\python.exe scripts/upload_legislation.py --commit` faz upload via `upload_all_legislation()` e sincroniza com `knowledge_catalog`. Output tabular: `filename | size | uri | catalog_id | status`. Idempotente por SHA-256 (uploader original ja cuida).

### Leg.4 -- Smoke tests + fixture

`tests/fixtures/regulatory_queries.json` carrega 8 Q&A canonicas cobrindo:
- dose THC / concentracao (RDC 327)
- validade prescricao (RDC 660 Art.7 §5)
- isencao registro (RDC 660 Art.1, 3, 4)
- uso pessoal Art.28 (Lei 11.343)
- prazo cadastro (RDC 660 Art.8)
- indicacoes pediatricas CFM (CFM 2.113)
- epilepsia refrataria + canabidiol (CFM 2.113)
- gestante / contraindicacao (RDC 660 + CFM)

`tests/test_regulatory_routes.py` ganhou 3 testes novos:
- `test_fixture_has_at_least_six_canonical_queries` -- valida formato.
- `test_query_legislation_smoke_with_mocked_gemini` -- mocka Gemini com `mock_answer` da fixture e valida pipeline HTTP + matching de keywords.
- `test_query_legislation_real_gemini_smoke` -- `@pytest.mark.skipif(not GOOGLE_API_KEY)` + skip secundario se base nao subida.

### Leg.5/Leg.6 -- Schema do manifesto + propagacao

`sources.json` ganhou tres campos novos (todos opcionais para back-compat):
- `publication_date: "YYYY-MM-DD"` (RDC 327: 2019-12-09; RDC 660: 2022-03-30; Lei 11.343: 2006-08-23; CFM 2.113: 2014-12-16)
- `norm_status: "vigente"` em todas as 4 normas core (decisao do coordenador)
- `revoked_by: null` em todas (nenhuma das 4 esta revogada)

`legislation_catalog.infer_legislation_metadata` extrai `norm_status` quando presente e o passa para o INSERT/UPDATE da `knowledge_catalog` (coluna `norm_status` ja existe desde a migration 016). `revoked_by` e `publication_date` ficam no record dict para downstream (UI/auditoria), mas nao escrevem coluna ainda -- coluna `knowledge_catalog.published_date` existe mas o backfill amplo via manifesto fica para C5 da Sprint 4.

### Custo Gemini observado

**Smoke real bloqueado por quota free-tier no dia do trabalho** (HTTP 429 RESOURCE_EXHAUSTED com `generate_content_free_tier_input_token_count limit: 0`). A estimativa do briefing (~$0.20/dia em piloto) permanece valida no plano. Quando a quota for liberada / migrada para tier pago, basta rodar:

```bash
env\Scripts\python.exe scripts/upload_legislation.py --commit
env\Scripts\python.exe -m pytest -k test_query_legislation_real_gemini_smoke -v
```

e capturar `usage.total_tokens` retornado pelo handler `/regulatory/query`.

## Proximos passos -- Frente C (C3-C5) para Sprint 4

- **C3** Validar `AgenteExtrator` no pipeline ponta-a-ponta (PubMed -> classificacao -> ingestao no knowledge_catalog). C6 ja entregou o auto-ingest durante atendimento; falta o gatilho administrativo de batch + UI no painel admin.
- **C4** Ativar `knowledge_monitors` (cron periodico para deteccao de novos artigos/normas em fontes monitoradas). Modelagem ja existe; falta o worker e botao "executar agora" no admin.
- **C5** Frontend admin: expor `POST /regulatory/upload` (botao em painel admin), expor consulta regulatoria com historico de queries, expor lista de normas com `norm_status`, e dashboard de monitores ativos.
- **Sprint 4 Leg.X (opcional)** Apontar uploader para `sanitized_filename` quando disponivel e medir economia real de tokens (estimativa: ~68% no in/out de payload, reducao analoga no input_tokens do Gemini).

## Arquivos tocados

- `data/legislation/sources.json` -- schema estendido
- `data/legislation/RDC_660_2022_ANVISA_sanitized.md` -- NOVO
- `data/legislation/Lei_11_343_2006_Planalto_sanitized.md` -- NOVO
- `data/legislation/Resolucao_CFM_2113_2014_sanitized.md` -- NOVO
- `data/legislation/README.md` -- atualizado com sanitizacao + schema do manifesto
- `scripts/sanitize_legislation_markdowns.py` -- NOVO
- `scripts/upload_legislation.py` -- NOVO
- `src/knowledge/legislation_catalog.py` -- propaga `norm_status` do manifesto
- `tests/fixtures/regulatory_queries.json` -- NOVO
- `tests/test_regulatory_routes.py` -- +3 testes (fixture + mock + real-skipif)
- `docs/sprints/sprint_3_Legislacao.md` -- ESTE doc
- `docs/22_EXECUTIVE_BACKLOG.md` -- Frente C C1/C2 marcados resolvidos
