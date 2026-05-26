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
