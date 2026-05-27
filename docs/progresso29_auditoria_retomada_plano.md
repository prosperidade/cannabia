# Progresso 29 - Auditoria de retomada e plano de continuidade

Data: 2026-05-25
Branch auditada: `main`
Modo: leitura + validacao + correcao pontual de permissao financeira

## 1. Escopo

Auditoria feita em duas passadas:

1. Retomada operacional a partir de
   `docs/progresso16_sprints_6_7_8_fechamento.md` ate os docs mais recentes
   (`progresso28` + sprints 2/3).
2. Leitura estruturada da pasta `docs` de `00` ate `28.*`, para alinhar o
   plano tecnico com a visao completa do ecossistema.

Cruzamentos feitos com:

- migrations 000..046
- backend Flask (`src/`)
- frontend Next (`frontend/`)
- scripts operacionais (`scripts/`, `render.yaml`, `.github/workflows/ci.yml`)
- testes existentes

Objetivo: separar o que ja foi fechado do que ainda e divida real, bug
silencioso ou pendencia operacional antes de seguir para novas features.

### 1.1 Sintese dos documentos 00-28

- `00-14` consolidam a tese central: a CannabIA nao deve ser reconstruida do
  zero. O produto e uma plataforma white-label multi-tenant para clinicas,
  associacoes e medicos, com jornada completa de paciente, medico,
  acompanhamento, IA assistiva, RAG, financeiro e auditoria.
- `15-22` transformam a visao em execucao tecnica: inventario real,
  migracao progressiva `clinic_id -> tenant_id`, Next.js como frontend alvo,
  contrato API Flask/Next, arquitetura de agentes com caminho
  `specialist-first` e backlog executivo por frentes.
- `23-27` elevam o SCC a diferencial estrategico: Governance Hub, SOPs,
  rastreabilidade seed-to-patient, farmacovigilancia, Evidence Engine,
  Regulatory Reporting, eventos append-only, hash chaining, ancoragem publica
  e templates regulatorios versionados.
- `28.0`, `28.1` e `28.A` ampliam o escopo institucional: quatro blocos
  funcionais, cinco PJs, segregacao patrimonial, principios inegociaveis,
  documento vivo e arquitetura em camadas. Para o codigo, a implicacao mais
  direta e preparar `tenant.type` para representar plataforma, instituto,
  federacao, associacoes, clinicas franqueadas, laboratorios e cooperativas.

Leitura executiva: a ordem correta continua sendo estabilizar a plataforma
tecnica antes de expandir. Sem suite confiavel, backup validado, seguranca de
segredos e roles coerentes, nao existe base solida para piloto, SCC em
producao ou arquitetura institucional mais ampla.

## 2. Estado consolidado do sistema

### 2.1 Fechado de fato

- Multi-tenancy, tenant branding, integracoes por tenant e quotas foram
  implementados.
- Financeiro/Pix existe no backend e frontend.
- SCC dev puro foi fechado: governance, membros, qualidade, rastreabilidade,
  farmacovigilancia, regulatory reporting, templates, evidence engine,
  anchoring mock/dispatchers, dashboards e compliance overview.
- App da clinica foi reorganizado com roles refinadas:
  `Admin`, `AdminClinica`, `Medico`, `Recepcao`, `Financeiro`, `Paciente`.
- App paciente deixou de ter 404 em `/p/consultas` e `/p/documentos`, mas
  `/p/documentos` ainda e placeholder funcionalmente honesto.
- Base cientifica global e colaborativa existe, com autoria e deletes por regra.
- C6 e C7 foram fechados no codigo: auto-ingest PubMed e agregacao clinica
  anonimizada.
- Migrations locais aplicadas ate `046_prompt_registry_alignment.sql`.
- CI existe e roda backend + frontend typecheck.

### 2.2 Baseline local observado

- `schema_migrations`: 46 registros, head `046`.
- `npx tsc --noEmit`: passou.
- Suite focada recomendada no progresso27: 65 passed.
- Suite completa antes da Sprint A: `1784 passed, 1 failed, 1 error`.
- Suite completa apos Sprint A local: `1802 passed, 1 skipped`.

Falhas anteriores da suite completa:

1. `tests/test_regulatory_routes.py::test_query_legislation_real_gemini_smoke`
   tentou usar Gemini real porque `GOOGLE_API_KEY` esta configurada no `.env`.
   Falhou com `[WinError 10061]` depois de 3 tentativas. Isso e fragilidade de
   teste: smoke real nao deveria rodar por padrao so porque a chave existe.
2. `tests/test_template_engine.py::TestRegistryLoader::test_registry_ausente_levanta_template_engine_error`
   falhou no setup de `tmp_path` por `PermissionError` em
   `%LOCALAPPDATA%/Temp/pytest-of-Administrador`. Isso parece estado local do
   Windows, nao bug do produto, mas bloqueia a suite ate limpar/corrigir o temp.

## 3. Achados por prioridade

### P0 - Corrigir antes de sprint funcional

#### P0.1 Backup ainda e risco operacional principal - automatizado em 2026-05-25

`progresso28` documenta que dumps pre-incidente tinham 0 bytes e que a
reconstrucao local so foi possivel por migrations/seeds, nao por restore real.
O controle de validacao tripla tinha sido feito manualmente. Em 2026-05-25
virou script local canonico.

Evidencias:
- `docs/progresso28_docker_recon_pos_incidente.md`: BUG-001 e follow-up F1.
- `backups/postgres/CHECKSUMS.txt`: ha checksum do dump pos-rebuild.
- `scripts/backup_postgres_validated.py`: cria/valida dump com tamanho,
  `pg_restore --list` e SHA-256.
- `docs/BACKUP_AND_DISASTER_RECOVERY.md`: atualizado com comando canonico.

Risco residual: ainda falta agendar envio/armazenamento off-site. A geracao
local validada ja nao deve aceitar dump silenciosamente vazio.

Status:
- Dump pos-rebuild validado: 408382 bytes, 1041 linhas em `pg_restore --list`.
- Novo dump local validado: `cannabia_20260525_162627.dump`, 415707 bytes,
  1043 linhas em `pg_restore --list`.
- Checksum registrado em `backups/postgres/CHECKSUMS.txt`.
- Pendente: job agendado/off-site.

#### P0.2 Teste real de Gemini esta acoplado ao ambiente local - corrigido em 2026-05-25

O smoke real de legislacao roda quando `GOOGLE_API_KEY` existe. Em ambiente
com chave configurada mas sem rede/quota, a suite completa quebra.

Evidencia:
- `tests/test_regulatory_routes.py::test_query_legislation_real_gemini_smoke`
  falhou com HTTP 500 apos 3 tentativas reais.
- `docs/sprints/sprint_3_Legislacao.md` ja registra que esse smoke depende
  de quota e deveria ser condicional.

Status:
- Gate alterado para exigir `RUN_REAL_GEMINI_SMOKE=1` alem de
  `GOOGLE_API_KEY`.
- Falha 5xx no smoke real vira `pytest.skip`, para nao quebrar suite local/CI
  por rede/quota.
- Contrato default permanece mockado.
- Validado na suite completa: 1 skip esperado.

#### P0.3 Temp do pytest no Windows bloqueia suite completa - corrigido em 2026-05-25

Erro em `%LOCALAPPDATA%/Temp/pytest-of-Administrador` impediu fixture `tmp_path`.

Status:
- Removida a unica dependencia de `tmp_path` em `tests/test_template_engine.py`.
- O teste agora usa um caminho inexistente deterministico em `tests/fixtures`,
  sem criar diretorio temporario.
- Validado na suite completa: sem erro de temp.

#### P0.4 Role `Financeiro` ve telas que backend bloqueia - corrigido em 2026-05-25

O sidebar mostra `Faturamento`, `Financeiro`, `Campanhas` e possivelmente
`Estoque` para role `Financeiro` (`frontend/lib/nav.ts:119-127`). A auditoria
confirmou que havia bug real no backend: endpoints financeiros ainda autorizavam
`Admin`, `Medico`, `Atendente` (normalizado para `Recepcao`) e nao `Financeiro`.

Regra consolidada apos correcao: superficies financeiras/campanhas/estoque
autorizam `Admin`, `AdminClinica` (incluindo dono de clinica via
`is_clinic_admin=True`) e `Financeiro`. `Medico` comum, `Recepcao` e alias
legado `Atendente` nao acessam financeiro.

Evidencias:
- `src/web/routes/payments.py`: decorators migrados para `FINANCIAL_ROLES`.
- `src/web/routes/org_management.py`: estoque, faturamento e financeiro migrados
  para `FINANCIAL_ROLES`.
- `src/web/routes/campaigns.py`: gate de campanhas migrado para role financeira.
- `frontend/lib/nav.ts:119-127`.
- `tests/test_financial_role_access.py`: regressao de roles permitidas/bloqueadas.

Risco anterior: usuario financeiro entrava pela navegacao correta, mas recebia
403 nas telas centrais do seu papel.

Status:
- Corrigido para pagamentos, estoque, faturamento, financeiro e campanhas.
- Teste focado: `17 passed` em `tests/test_financial_role_access.py`.

#### P0.5 Segredos em configuracoes migrados para fluxo seguro local

`tenant_integrations` tem criptografia, mas `tenant_settings` nasceu como JSONB
flexivel e a propria migration 039 documenta campos sensiveis no MVP. O route
`clinic_config.py` agora mascara, migra e limpa parte dos secrets para
integrations como fluxo defensivo, nao apenas compatibilidade.

Evidencias:
- `migrations/039_tenant_settings.sql:20-23` documenta chaves sensiveis no JSONB.
- `src/web/routes/clinic_config.py` tem `_legacy_secret_updates` e
  `_scrub_legacy_secret_settings`.
- `src/repositories/tenant_settings_repository.py` criptografa em
  `tenant_integrations`.

Acao executada:
- PATCH de configuracao ignora placeholders mascarados (`***` e `********`) e
  nao trata placeholder como segredo real.
- Segredo legado encontrado em `tenant_settings.settings` e copiado para
  `tenant_integrations` antes da limpeza do JSONB; se a persistencia
  criptografada falhar, o legado permanece para nova tentativa.
- Admin de tenant tambem ignora placeholders mascarados nos campos sensiveis.
- Testes cobrem o parsing de segredo mascarado e a preservacao de string vazia
  como limpeza explicita.

Pendencia residual:
- Rodar consulta/migracao em ambiente com dados reais para confirmar se ainda
  existe segredo historico em `tenant_settings.settings` e limpar com backup
  validado antes.

### P1 - Proxima passada de produto/engenharia

#### P1.1 Integracoes reais ainda sao stubs

O produto ja tem arquitetura de dispatcher, mas as integracoes externas reais
seguem pendentes:

- VigiMed/Notivisa: `_ProductionVigiMedClient` e `_ProductionNotivisaClient`
  levantam erro claro.
- Polygon: `_ProductionPolygonClient.anchor()` ainda levanta erro.
- OpenTimestamps: `_ProductionOtsClient.stamp()` ainda levanta erro.
- SMS: campanha SMS levanta `NotImplementedError`.

Evidencias:
- `src/integrations/vigimed.py:190-211`.
- `src/integrations/polygon_anchor.py:178-195`.
- `src/integrations/opentimestamps.py:122-140`.
- `src/services/campaign_service.py:544-571`.

Acao:
- Manter providers `mock` como default dev/CI.
- Antes de piloto regulatorio real, escolher uma integracao por sprint:
  ANVISA primeiro se requisito de piloto; Polygon/OTS se requisito de prova.
- Na UI, esconder/desabilitar SMS se o backend nao suporta.

#### P1.2 `.env.example` esta atrasado em relacao ao runtime

`render.yaml` e o codigo usam variaveis que nao aparecem em `.env.example`,
incluindo Sentry, LGPD, anchoring, Polygon, ANVISA notification, prompt admin,
legislation dir e case aggregate.

Evidencias:
- `render.yaml:74-87`, `93-114`.
- `src/services/anchoring_service.py` usa `ANCHORING_PROVIDER`.
- `src/integrations/polygon_anchor.py` usa `POLYGON_*`.
- `src/integrations/vigimed.py` usa `ANVISA_NOTIFICATION_PROVIDER`.
- `src/knowledge/case_aggregator.py` usa `CASE_AGGREGATE_MIN_K`.
- `src/knowledge/google_files.py` usa `LEGISLATION_DIR`.
- `src/ai/prompt_registry.py` usa `FF_PROMPT_REGISTRY_ADMIN`.

Acao:
- Atualizar `.env.example`.
- Adicionar teste/doc check simples que compara envs documentadas vs envs
  referenciadas em codigo critico.

#### P1.3 Frontend ainda tem placeholders ou telas cosmeticas

Partes do app ainda sao honestamente incompletas ou simuladas:

- `/p/documentos`: pagina existe, mas mostra "Em construcao".
- `/med/onboarding`: comentario explicito "All data is mock/UI only" e TODO
  de persistencia.
- `/med/consulta/[id]`: chat cosmetico, sem WebSocket real.
- `/org/relatorios`: varios KPIs caem para `--` quando endpoint nao entrega.

Acao:
- Definir se essas telas entram no MVP do piloto.
- Se nao entram, esconder da navegacao por role/feature flag.
- Se entram, criar endpoints e testes de contrato por tela.

#### P1.4 Paginacao legacy tem Sunset futuro

`?legacy=1` ainda existe com Sunset em 2026-08-01 e `paginated=1` segue como
opt-in em endpoints Tier-2.

Acao:
- Listar consumidores frontend restantes.
- Remover fallback legacy antes de 2026-08-01.

### P2 - Dividas tecnicas e qualidade

#### P2.1 `except Exception` ainda e amplo em muitos pontos

Houve melhora em alguns endpoints, mas ainda ha captura ampla em AI, knowledge,
routes e integrations. Parte e defensiva, parte pode mascarar bug real.

Acao:
- Tratar por dominio, comecando por rotas chamadas pelo frontend e agentes IA.
- Converter erro esperado para excecoes tipadas.
- Manter `Exception` apenas em bordas com log estruturado e teste.

#### P2.2 `src/ai/telemetry.py` ainda tem `print`

Evidencia:
- `src/ai/telemetry.py:12`.

Acao:
- Trocar por logger ou remover se debug morto.

#### P2.3 Coverage global nao e criterio ainda

Suite completa mostrou cobertura global de 58%, mas varios modulos sao de
integracao/opcionais. O problema nao e o numero bruto; e ausencia de gate por
modulo critico.

Acao:
- Definir baseline por trilha: auth/security, patient portal, payments,
  knowledge, regulatory, agents.
- Adicionar `--cov-fail-under` so depois de estabilizar baseline.

## 4. Plano recomendado

### Sprint A - Recuperabilidade e baseline verde - concluida localmente em 2026-05-25

1. Corrigido gate do smoke real Gemini (`RUN_REAL_GEMINI_SMOKE=1`).
2. Removida dependencia de `tmp_path` que quebrava no Windows local.
3. Automatizado backup validado em `scripts/backup_postgres_validated.py`.
4. Criado `docs/LOCAL_DEV.md`.
5. Atualizado `.env.example`.
6. Suite completa verde localmente.

Criterio de pronto:
- `pytest -q`: `1802 passed, 1 skipped`.
- `npx tsc --noEmit`: verde.
- Dump validado por tamanho, `pg_restore --list` e checksum.

Pendencia residual operacional:
- Agendar job/off-site para export logico mensal validado.

### Sprint B - Segredos e endurecimento financeiro

Status: concluida localmente em 2026-05-25.

1. Cleanup/migracao defensiva de secrets de `tenant_settings` ajustada.
2. Backend ignora placeholders mascarados como valor de segredo real.
3. Endpoints legados com `Atendente` foram migrados para `Recepcao` ou roles
   refinadas conforme superficie.
4. Areas financeiras seguem restritas a `Admin`, `AdminClinica`, `Financeiro`
   e medico dono da clinica quando o contexto exigir dono.

Criterio de pronto:
- Nenhum segredo novo persiste em JSONB claro.
- Testes backend cobrem segredos e roles refinadas remanescentes.
- Validacao local: `pytest -q` com `1804 passed, 1 skipped`.
- Validacao frontend: `npx tsc --noEmit` verde.

Pendencia residual operacional:
- Executar auditoria SQL nos bancos reais para identificar segredo legado em
  JSONB antes de considerar a migracao historica encerrada.

### Sprint C - Produto visivel do piloto

1. Decidir MVP de `/p/documentos`, onboarding medico, relatorios e chat de
   consulta.
2. Esconder o que nao for MVP.
3. Implementar dados reais para o que ficar visivel.
4. Revisar mensagens de "em construcao" para nao parecer produto quebrado.

### Sprint D - Integracoes externas

Escolher uma linha:

- ANVISA/VigiMed se o piloto regulatorio exigir notificacao real.
- Polygon/OTS se a prioridade for prova publica de integridade.
- SMS se campanhas multicanal forem requisito comercial.

Nao fazer as tres em paralelo; cada uma depende de credencial/provedor e teste
operacional proprio.

## 5. Ordem executiva sugerida

1. P0.2 + P0.3: suite verde e confiavel.
2. P0.1: backup validado automatizado.
3. Auditoria SQL em dados reais para P0.5 historico.
4. P1.2: env docs alinhadas.
5. P1.3: esconder ou completar placeholders visiveis.
6. Integracoes reais conforme decisao de piloto.

## 6. Notas de cautela

- Nao iniciar P5 (refatoracao profunda dos agentes) antes de suite verde e
  backup confiavel. A area de agentes e grande e sensivel; sem baseline limpo,
  qualquer regressao ficara cara de diagnosticar.
- Nao ligar providers reais (`ANCHORING_PROVIDER=polygon|ots`,
  `ANVISA_NOTIFICATION_PROVIDER=vigimed|notivisa`) em producao ate os clients
  reais deixarem de ser stubs.
- Nao habilitar `LGPD_PURGE_ENABLED=true` sem OK juridico e dry-run revisado.

## 7. Atualizacao 2026-05-25 (noite) — execucao das Sprints A, B, C e D

Esta secao foi adicionada apos a execucao das sprints planejadas neste
documento, para refletir o estado final do dia.

### 7.1 Sprints A, B, C — MERGED em main

| PR | Merge | Cobre |
|----|-------|-------|
| #39 `feat/sprint-A-baseline-recoverability` | `9f4eb3b` | P0.1, P0.2, P0.3 + bootstrap (`.env.example` parcial, `docs/LOCAL_DEV.md`) |
| #40 `feat/sprint-B-secrets-financial` | `ab91c6e` | P0.4, P0.5 + alias Atendente->Recepcao/AdminClinica + `tests/test_financial_role_access.py` |
| #41 `feat/sprint-C-mvp-pilot` | `0fe9112` (HEAD main) | C.1 esconder `/p/documentos` + C.2 chat input desativado + C.3 `/org/relatorios` sem mocks + C.4-base `/med/onboarding` persistido (migration 047_medical_profiles + endpoint POST + 10 tests) |

### 7.2 Sprint D - "Quitar dividas tecnicas" - 3 PRs abertas

A "Sprint D - Integracoes externas" descrita na secao 4 foi adiada
(renomeada `Sprint E` abaixo). Em seu lugar foi executada uma Sprint D
focada em quitar as dividas tecnicas P1.2, P1.4, P2.2, P2.3 e fechar a
onda 2 do Sprint C (upload real).

| PR branch | HEAD | Cobre |
|-----------|------|-------|
| `feat/sprint-D-quick-wins` | `dbe461b` | Q1 P2.2 marcado como falso positivo + Q2 P1.4 remove `?legacy=1` honrando antecipadamente Sunset 2026-08-01 + Q3 P1.2 `tests/test_env_docs_alignment.py` (capturou 7 envs SENTRY/LEGISLATION/CASE_AGGREGATE/FF_PROMPT que Sprint A deixou faltar; adicionadas em `.env.example`) |
| `feat/sprint-D-storage-r2` | `200db61` | M1 onda 2 da Sprint C: `src/infra/storage.py` com providers plugaveis (noop/local/r2) + endpoint POST `/api/v1/med/onboarding/upload/<field>` multipart (5MB, pdf/jpg/png) + `boto3>=1.34.0` opcional + 7 tests storage + 10 tests upload + frontend `uploadOnboardingDocument()` + `UploadZone` reativado |
| `feat/sprint-D-coverage-baseline` | `76d7cc9` | M3 P2.3: gate global `--cov-fail-under=55` em `pytest.ini` + baseline documentado por trilha (12 maduras >=80%, 8 estaveis 60-79%, 14 pendentes <50%) |

Validacao local na sessao:
- Sprint A+B+C juntas (relatado pelo usuario): `pytest -q` 1804 passed, 1 skipped + `tsc --noEmit` verde
- Sprint D Quick Wins: 1813 passed, 1 skipped + tsc verde
- Sprint D Storage R2: 1831 passed, 1 skipped (+17 testes novos) + tsc verde
- Sprint D Coverage Gate: 1814 passed, 1 skipped, cobertura 58.56% > 55%

### 7.3 Status atualizado por achado

| Achado | Status apos sessao | PR de origem |
|--------|---------------------|--------------|
| P0.1 Backup validado triplo | concluido + script canonico | Sprint A #39 |
| P0.2 Gate Gemini smoke | concluido | Sprint A #39 |
| P0.3 tmp_path windows | concluido | Sprint A #39 |
| P0.4 Roles financeiras | concluido + 17 tests regressao | Sprint B #40 |
| P0.5 Segredos defensivos | concluido (residual: auditoria SQL em prod) | Sprint B #40 |
| P1.1 Integracoes reais (Polygon/OTS/ANVISA/SMS) | nao atacado — depende de credenciais externas | (Sprint E) |
| P1.2 `.env.example` alinhado | concluido + test automatico | Sprint D quick-wins |
| P1.3 Frontend placeholders | concluido (3 escondidos + 1 implementado + uploads reais) | Sprint C #41 + Sprint D storage |
| P1.4 Paginacao legacy Sunset | concluido (removido antecipadamente) | Sprint D quick-wins |
| P2.1 `except Exception` amplo | adiado para sessao dedicada (~2h) | (Sprint D-2 M2 futura) |
| P2.2 `print` em telemetry.py | falso positivo (era docstring) | Sprint D quick-wins |
| P2.3 Coverage gate | concluido (gate 55% global + baseline por trilha) | Sprint D coverage-baseline |

### 7.4 Sprint E - Integracoes externas (renomeada da Sprint D original)

A Sprint D originalmente planejada nesta secao 4 foi renumerada para
Sprint E, ja que o nome "Sprint D" passou a referenciar o trabalho de
quitar dividas tecnicas acima. Escopo inalterado:

- ANVISA/VigiMed se o piloto regulatorio exigir notificacao real.
- Polygon/OTS se a prioridade for prova publica de integridade.
- SMS se campanhas multicanal forem requisito comercial.

### 7.5 Pendencias residuais apos hoje

- **M2 / P2.1 except Exception cleanup** — 146 occs em 59 arquivos.
  Atacar em rotas frontend-facing (api_v1, clinic_config, payments,
  patient_portal, knowledge). Adiado por escolha de escopo da sessao.
- **Auditoria SQL P0.5 historico** — operacional, precisa acesso bancos
  reais (Render/staging).
- **Backup off-site agendado (P0.1 onda 2)** — operacional.
- **Credenciais Cloudflare R2** — codigo Sprint D storage-r2 esta pronto,
  esperando `R2_ACCOUNT_ID`/`KEY`/`SECRET`/`BUCKET` para ativar storage real
  em prod (default `noop` ate la).
- **BUG-001 dumps zerados** — investigacao pendente (memoria
  `project_bug_001_dumps_zerados.md`).
- **C6 / C7** (agentes ingerindo + agregacao anonimizada) — fechados no
  codigo, pendente validacao operacional.
- **P5 refatoracao agentes IA** — por ultimo (decisao 2026-04-27 +
  cautela secao 6).

## 8. Atualizacao 2026-05-26 (manha) — fechamento da Sprint D

### 8.1 Sprint D 100% merged em main

As 3 PRs Sprint D que ainda estavam abertas foram fechadas nesta sessao,
completando o ciclo iniciado em 2026-05-25.

| PR | Merge | Cobre |
|----|-------|-------|
| #43 `feat/sprint-D-quick-wins` | `c040d3f` | Q1 P2.2 + Q2 P1.4 + Q3 P1.2 |
| #44 `feat/sprint-D-coverage-baseline` | `d86e112` | M3 P2.3 (gate global 55%) |
| #45 `feat/sprint-D-docs-update` | `2388fd0` | secao 7 do progresso29 + arquivo sprint_1_D_PR |

PR adicional unrelated mergeada na mesma janela:
- #18 `feat/cannabia-docs-4821243085080745684` — 4 docs novos em `docs/`
  (CANNABIA_README, DATABASE_MAPPING, TECHNICAL_CONTEXT, WHATSAPP_FLOW).
  Sem impacto em codigo, fora do escopo Sprint D.

### 8.2 Resolucao de conflito em quick-wins

`feat/sprint-D-quick-wins` foi criada antes do merge de `feat/sprint-D-storage-r2`
(PR #42). Ambas alteravam `.env.example` em regioes proximas, o que produziu
conflito real (nao corrupcao de historico).

Resolucao aplicada em `56424ca`:
- Mantidos os dois blocos sem perda.
- Bloco STORAGE/R2 ficou primeiro (chegou em main antes via #42).
- Bloco SENTRY/KNOWLEDGE/FF_PROMPT_REGISTRY_ADMIN ficou em seguida (P1.2).
- Validacao local pos-resolucao: `pytest 1830 passed, 1 skipped` +
  `tsc --noEmit` verde.

### 8.3 Baseline atual em main

Suite completa em main pos-merges:
- `pytest -q`: 1830 passed, 1 skipped, 0 errors.
- Coverage global: 58.84% (gate 55% atendido).
- `npx tsc --noEmit`: verde.

### 8.4 Anomalia observada (nao bloqueante)

Em uma das execucoes locais durante a sessao apareceu:
`ERROR tests/test_evidence_service.py::TestSummarizeFollowupResponses::test_empty_period_returns_zeros`

Caracteristicas:
- Apareceu apenas em uma execucao da suite completa.
- Reexecucao isolada do mesmo teste: PASSED.
- Reexecucao da suite completa imediatamente em seguida: 1830 passed, sem error.

Diagnostico provisorio: pollution de estado entre testes (ordem-dependente),
nao bug do produto. Adicionar ao backlog M2/qualidade para reproduzir com
`pytest --randomly-seed=last` ou isolar fixtures se reaparecer no CI.

### 8.5 Estado de cleanup

- 4 branches `feat/sprint-D-*` deletadas no remoto e local.
- `main` em `8d3fde2` (HEAD pos-merges).
- Backlog residual permanece como na secao 7.5: M2 except cleanup,
  auditoria SQL P0.5, backup off-site, credenciais R2, BUG-001 dumps,
  C6/C7 validacao operacional, Sprint E integracoes externas, P5 agentes IA.

## 9. Atualizacao 2026-05-26 (tarde) — M2 except cleanup (parcial)

### 9.1 Ataque ao P2.1 em 7 PRs paralelas

O cleanup do antipadrao `except Exception` (P2.1) foi atacado em 7 PRs
sequenciais ao longo de 2026-05-26, com trabalho coordenado entre Claude
e Codex. Estado inicial: 146 occs em 59 arquivos. Estado final: 90 occs
em 45 arquivos. **Reducao de 56 occs (-38%)** e 14 arquivos limpos.

| PR | Merge | Branch | Cobre |
|----|-------|--------|-------|
| #46 | `97f8f6a` | `feat/sprint-D-m2-silent-swallows` | M2.1: 9 silent swallows (app/validators/legislation_catalog/tasks/pharmacovigilance/governance/payments/knowledge x2) → narrow `(TypeError, ValueError)`, `OSError`+`JSONDecodeError`, `RuntimeError` para auth-ctx, log.debug/warning |
| #47 | `3336c03` | `feat/sprint-D-m2-web-routes-narrow` | M2.2 base: clinic_config + knowledge (3) + compliance (2) + patient_portal (1) — add `OperationalError → 503` antes do catch-all em 7 rotas |
| #48 | `a040e46` | `feat/sprint-D-m2-knowledge-config` | M2.2 extensao: knowledge_routes (15 → 7) + clinic_config narrow para `(DatabaseError, ValueError, RuntimeError)` |
| #49 | `3d485b7` | `feat/sprint-D-m2-payments` | M2.2: payments.py (4 → 0) — webhooks com `(DatabaseError, ValueError)` |
| #50 | `e4be485` | `feat/sprint-D-m2-api-v1` | M2.2: api_v1.py (2 → 0) narrow para excecoes tipadas + `RuntimeError` |
| #51 | `9ed30ac` | `feat/sprint-D-m2-org-management` | M2.2: org_management.py (8 → 0) — todos os endpoints admin org com `OperationalError → 503` + `DatabaseError → 500` |
| #52 | `22b4a22` | `feat/sprint-D-m2-admin-clinical` | M2.2: admin_users.py + clinical_intelligence.py — 4 endpoints, mantem 503 para OperationalError, 500 para esperadas |

### 9.2 Padroes aplicados

O cleanup adotou tres padroes consistentes (em ordem do mais especifico
para o mais amplo):

1. **Narrow para excecao tipada esperada** quando o erro tem causa unica:
   - Parsing/conversao de tipos → `(TypeError, ValueError)`
   - IO de arquivo → `OSError`, `json.JSONDecodeError`
   - DB connection/timeout → `psycopg2.OperationalError → 503`
   - DB query/integrity → `psycopg2.DatabaseError → 500`
   - Auth context fora do request → `RuntimeError`

2. **Catch-all em borda com log estruturado**: preservado nas funcoes que
   sao genuinamente boundary (route handlers que tem que devolver algo)
   ou em integracoes externas. Sempre com `logger.error(..., exc_info=True)`.

3. **Add 503 antes do catch-all**: padrao mais comum em rotas frontend-facing.
   `OperationalError` (DB indisponivel) vira 503 com mensagem "Servico
   temporariamente indisponivel". Catch-all permanece como ultima rede,
   mas agora so cobre erros nao-DB.

### 9.3 Trabalho ainda em aberto

90 occs restantes em 45 arquivos, distribuidas:

| Dominio | Occs | Top arquivos | Prioridade M2 |
|---------|------|--------------|---------------|
| **AI agents/pipeline** | 26 | `agents/extrator.py` (9), `ai/chains.py` (4), `agents/regulatorio.py` (3), `agents/cientifico.py` (2), `agents/base.py` (2) | Alta (M2.3 candidato) |
| **Web routes restantes** | 21 | `regulatory.py` (4), `system.py` (3), `prescriptions.py` (3), `admin_agents.py` (3), `governance.py` (2), `telemetry.py` (2) | Media |
| **Infra** | 14 | `health.py` (5), `observability.py` (3), `tasks.py` (2), `database.py` (2) | Baixa (bordas defensivas OK) |
| **Services** | 13 | `anchor_upgrade_service.py` (2), `billing_service.py` (2), `campaign_service.py` (2), `message_service.py` (2) | Media |
| **Knowledge** | 9 | `google_files.py` (6), `pubmed.py` (2), `auto_ingest.py` (1) | Media (concentrado em google_files) |
| **Integrations** | 4 | vigimed, polygon_anchor, opentimestamps, email (1 cada) | Baixa (ja sao bordas) |
| **Outros** | 4 | `app.py` (1), `tenancy.py` (2), `repositories/anamnesis_repository.py` (1) | Baixa |

Recomendacao: proxima rodada (M2.3) atacar **AI agents/pipeline** porque
- Concentracao em 5 arquivos (chains, extrator, regulatorio, cientifico, base)
- Agentes IA sao core do produto e tem alto valor de observabilidade
- Padroes ja conhecidos: graceful degradation de chamadas externas (PubMed, Gemini, OpenAI) — narrow para `requests.exceptions.RequestException`, `httpx.HTTPError`, `google.api_core.exceptions.*`, etc.

### 9.4 Baseline em main pos-7-PRs

- HEAD: `22b4a22`
- pytest -q: 1830 passed, 1 skipped (mesmo baseline pre-M2)
- Coverage: 58.84% (gate 55% atendido)
- tsc --noEmit: verde
- 6 branches sprint-D-m2-* deletadas remoto+local
- Comportamento publico API: inalterado para sucesso; rotas DB-touching agora
  retornam 503 em vez de 200-vazio quando Postgres cai

### 9.5 Pendencias residuais inalteradas

Mesma lista da secao 8.5, mas M2 agora parcialmente quitado. As 90 occs
restantes seguem como divida tecnica P2.1 a ser fechada em ondas
subsequentes (M2.3 AI agents recomendado; depois infra/services
conforme valor).

## 10. Atualizacao 2026-05-26 (noite) — M2.3 agentes IA

### 10.1 PR #53 merged: narrow em agentes IA

Continuacao do M2 com foco em chamadas externas dos agentes.

| PR | Merge | Arquivos | Mudanca |
|----|-------|----------|---------|
| #53 `feat/sprint-D-m2-ai-agents` | `95ec3c5` | extrator (5), regulatorio (1), cientifico (1) + boundary documentado em base | -7 occs |

### 10.2 Narrows aplicados

Chamadas externas com tipo conhecido:

| Arquivo / linha | Antes | Depois |
|-----------------|-------|--------|
| extrator.py:200 _search_pubmed | except Exception | `(requests.exceptions.RequestException, ValueError, KeyError)` |
| extrator.py:223 _fetch_pubmed_article | except Exception | `(requests.exceptions.RequestException, ValueError)` |
| extrator.py:258 ANVISA fallback | except Exception | `requests.exceptions.RequestException` |
| extrator.py:552 _check_monitor | except Exception | `(requests.exceptions.RequestException, ValueError)` |
| extrator.py:684 file read | except Exception | `OSError` |
| regulatorio.py:202 governance_service import guard | except Exception | `ImportError` |
| cientifico.py:148 ChromaDB ingest loop | except Exception | `(ImportError, ConnectionError, RuntimeError, ValueError)` |

### 10.3 Boundary mantido com documentacao

`base.py:127 register_to_knowledge_base` foi inicialmente narrowed para
`(ImportError, DatabaseError, TypeError, KeyError, ValueError)` mas o
teste `test_register_to_kb_is_fire_and_forget_on_exception` quebrou com
`RuntimeError`. A docstring do metodo declara explicitamente
**"Fire-and-forget: nunca levanta excecao"**. Boundary genuino — retornou
para `except Exception` com comentario explicando o contrato (docstring +
teste).

Isso valida a guidance da secao 7.5/8.5 do progresso29: "Manter Exception
apenas em bordas com log estruturado e teste".

### 10.4 Boundaries NAO tocadas em ai/agents (decisao explicita)

Estas seguem sendo cobertas pela diretriz de boundary defensivo:

- `chains.py` (4 wrappers de circuit breaker): chamadas LLM com
  `cb.record_failure() + raise`. Catch amplo necessario porque a libreria
  pode levantar qualquer tipo (openai.*, httpx.*, ConnectionError, etc.).
- `base.py:164 run` (top-level agent wrapper): registra `result.error` +
  `logger.error(..., exc_info=True)`. Contrato do agent runtime.
- `extrator.py` wrappers top-level (362, 367, 381, 620): ingest/upload
  com retorno estruturado dict.
- `regulatorio.py:167` (Gemini wrapper), `:398` (persist guard com
  `pragma no cover`).
- `cientifico.py:52` RAG search com graceful degradation.

### 10.5 Baseline atual em main

- HEAD: `95ec3c5`
- pytest -q: 1830 passed, 1 skipped, 0 errors
- Coverage: 58.61% (gate 55% atendido)
- tsc --noEmit: verde
- 83 occs except Exception em 45 arquivos (-7 desde inicio da sessao tarde,
  -63 desde inicio do M2 ontem)

### 10.6 Distribuicao residual atualizada

| Dominio | Antes (90) | Agora (83) | Restantes |
|---------|------------|------------|-----------|
| AI agents/pipeline | 26 | 19 | base (2), chains (4), extrator (4), regulatorio (2), cientifico (1), service/prompt_registry/prescriber/pipeline/guardrails (1 cada) |
| Web routes | 21 | 21 | inalterado — proxima onda candidata |
| Infra | 14 | 14 | inalterado (bordas defensivas, baixa prioridade) |
| Services | 13 | 13 | inalterado |
| Knowledge | 9 | 9 | inalterado |
| Integrations | 4 | 4 | inalterado (ja sao bordas) |
| Outros | 4 | 4 | inalterado |

Proxima onda recomendada: **M2.4 web routes restantes** (21 occs em
`regulatory.py` 4, `system.py` 3, `prescriptions.py` 3, `admin_agents.py`
3, `governance.py` 2, `telemetry.py` 2, outros 4). Padrao ja conhecido
do M2.2: `OperationalError → 503`, `DatabaseError → 500`, demais como
boundary defensivo.

## 11. Fechamento do dia 2026-05-26 (noite final)

### 11.1 Sumario executivo do dia

O dia abriu com 146 ocorrencias de `except Exception` em 59 arquivos
(P2.1 do progresso29). O dia fecha com **70 occs em 41 arquivos** —
uma reducao de **76 occs (-52%)** e 18 arquivos (-31%) totalmente
limpos ou reduzidos. Foram 10 PRs mergeadas em main mais 2 doc-updates
diretos em main.

### 11.2 PRs mergeadas hoje

| Ordem | PR | Merge | Wave | Conteudo |
|-------|----|-------|------|----------|
| 1 | #46 | `97f8f6a` | M2.1 | 9 silent swallows |
| 2 | #47 | `3336c03` | M2.2a | rotas base (clinic_config + knowledge + compliance + patient_portal) |
| 3 | #48 | `a040e46` | M2.2b | knowledge-config (codex) |
| 4 | #49 | `3d485b7` | M2.2c | payments (codex) |
| 5 | #50 | `e4be485` | M2.2d | api-v1 (codex) |
| 6 | #51 | `9ed30ac` | M2.2e | org-management (codex) |
| 7 | #52 | `22b4a22` | M2.2f | admin-clinical (codex) |
| 8 | #53 | `95ec3c5` | M2.3 | agentes IA (extrator + regulatorio + cientifico) |
| 9 | #54 | `87cc1cd` | M2.4 | rotas restantes (admin_agents + tenant_admin + historico + regulatory + system + governance) |
| 10 | #55 | `9347ede` | M2.5 | knowledge/google_files (3 narrows + 3 boundaries documentadas) |

Doc updates diretos em main:
- `e26bf23` secao 9 (M2.1+M2.2 fechamento)
- `2a493ad` secao 10 (M2.3 fechamento)
- `[este commit]` secao 11 (fechamento do dia + pendencias vivas)

### 11.3 Padroes consolidados (vale para amanha)

Tres padroes provaram funcionar bem nesta cadencia:

1. **Narrow para excecao tipada** (parsing, IO, DB, network):
   - Parsing: `(TypeError, ValueError)`, `json.JSONDecodeError`
   - IO: `OSError` (cobre FileNotFoundError, PermissionError, ConnectionError)
   - DB connection: `psycopg2.OperationalError → 503`
   - DB integridade: `psycopg2.IntegrityError` (UNIQUE/FK)
   - DB query generico: `psycopg2.DatabaseError → 500`
   - Auth flask_login fora request: `RuntimeError`
   - HTTP request: `requests.exceptions.RequestException`
   - Import opcional: `ImportError`

2. **Boundary defensivo mantido + `# noqa: BLE001` + comentario**: para
   retry loops, batch loops, fire-and-forget. O comentario justifica
   o catch amplo para futuros revisores.

3. **503 antes do catch-all em rotas DB-touching**: `except OperationalError`
   ANTES do `except Exception`, retorna `_error("database_unavailable", ..., 503)`
   preservando fallback do catch-all para outros tipos.

### 11.4 Lessons learned no dia

- **Codex coordenado em paralelo funcionou**: 5 PRs (#48-#52) entraram
  enquanto Claude trabalhava em #47. Padroes pre-estabelecidos
  (M2.1 + M2.2-base) ajudaram a manter consistencia.
- **Testes pegaram 2 boundaries genuinas**:
  - `base.py:127 register_to_kb` (M2.3): test_register_to_kb_is_fire_and_forget_on_exception
    quebrou com RuntimeError; docstring explicita "Fire-and-forget: nunca levanta
    excecao". Restaurado para `except Exception` com comentario.
  - `governance.py:383 create_rt` (M2.4): teste mockava RuntimeError em vez de
    IntegrityError. Atualizei tanto a rota (narrow para IntegrityError) quanto
    o teste (mock fiel ao tipo real). Melhoria de qualidade no teste tambem.
- **Conflito `.env.example` repetido**: PR #43 vs #42 deu conflito (Sprint D)
  mesma janela; PR de codex tambem teve conflito; sempre que multiplos PRs
  mexem em `.env.example` o merge precisa preservar ambos blocos.
- **Anomalia flaky `test_evidence_service`**: reapareceu 2 vezes hoje, sempre
  some na reexecucao. Diagnostico de pollution mantido (vide §8.4). Adicionar
  ao backlog para reproduzir com `pytest --randomly-seed=last`.

### 11.5 Baseline atual em main (fim do dia)

- HEAD: `9347ede`
- pytest -q: 1830 passed, 1 skipped, 0 errors (com 1 ERROR flaky esporadico documentado)
- Coverage global: 58.62% (gate 55% atendido)
- tsc --noEmit: verde
- Branches sprint-D-m2-* todas deletadas (11 PRs limpas)
- 70 occs `except Exception` em 41 arquivos

### 11.6 Distribuicao residual (70 occs — base para amanha)

| Dominio | Occs | Top arquivos | Recomendacao M2.6+ |
|---------|------|--------------|---------------------|
| AI agents/pipeline | 19 | chains.py (4), extrator.py (4), base.py (2), regulatorio.py (2), cientifico (1), service/prompt_registry/prescriber/pipeline/guardrails (1 cada) | **KEEP a maioria** — chains sao circuit breakers, base.py:164 e agent boundary, etc. Talvez 2-3 narrows possiveis. |
| Web routes | 19 | regulatory.py (2), telemetry.py (2), prescriptions.py (3), admin_agents.py (2), realtime_notifications (1), public_anchors (1) | **KEEP a maioria** — todas sao bordas com logger.exception ja narrowed antes. |
| Infra | 14 | health.py (5), observability.py (3), tasks.py (2), database.py (2), audit (1), telemetry_tasks (1) | **KEEP a maioria** — bordas de health/obs. Talvez 1-2 narrows. |
| Services | 13 | 9 files (2 cada em alguns, 1 em outros) | **NARROW possivel** — varias chamadas WhatsApp/email/SMS que podem narrow para network. |
| Knowledge | 6 | google_files (3 boundaries doc'd), pubmed.py (2), auto_ingest (1) | **NARROW possivel** em pubmed.py + auto_ingest. |
| Integrations | 4 | vigimed, polygon, ots, email (1 cada) | **KEEP** — sao bordas por design (raise tipo customizado depois). |
| Outros | 4 | app.py (1), tenancy.py (2), anamnesis_repository.py (1) | **KEEP** — bordas top-level. |

### 11.7 Pendencias vivas para amanha (e alem)

Priorizadas por valor:

1. **M2.6 (opcional) — services + knowledge** — ~19 occs com bom ROI
   esperado (chamadas externas em services + pubmed). Pode atacar amanha
   se quiser continuar M2.
2. **BUG-001 dumps zerados** — investigacao tecnica, nao depende de
   credenciais externas. Pode salvar proxima crise operacional. ~1-2h.
3. **Verify produto na pratica** — subir backend+frontend, rodar onboarding
   medico, testar 503 quando DB cai. Acumulamos ~10 PRs sem teste manual
   integrado. ~30-45min.
4. **Sprint E integracoes externas** — depende de credenciais (Polygon/OTS/
   ANVISA/SMS). Pode-se preparar o codigo aguardando secrets.
5. **Auditoria SQL P0.5 historico** — operacional, banco real (Render).
6. **Backup off-site agendado (P0.1 onda 2)** — operacional.
7. **Credenciais Cloudflare R2** — codigo pronto, aguardando R2_ACCOUNT_ID
   e cia para sair de `noop`.
8. **C6/C7 validacao operacional** — agentes ingerindo + agregacao
   anonimizada; codigo fechado, falta rodar em prod.
9. **Anomalia flaky test_evidence_service** — reproduzir com
   `pytest --randomly-seed=last` e isolar fixture culpada.
10. **P5 refatoracao agentes IA** — por ultimo (decisao 2026-04-27 +
    cautela secao 6).

### 11.8 Recomendacao para amanha

Sugestao de ordem ao retomar:

1. **Verify produto na pratica** (30-45min): valida que as 10 PRs do dia
   nao quebraram nada visivel.
2. **Decidir entre M2.6 vs BUG-001 vs Sprint E**: depende do apetite.
   M2.6 fecha mais divida tecnica mas com ROI decrescente (a maioria sao
   bordas legitimas). BUG-001 e investigacao pontual com alto valor
   defensivo. Sprint E e feature nova mas depende de secrets.

Para retomar: ler progresso29 secoes 8-11 + memoria
[[sprint-progress-2026-05-26-m2-parcial]].
