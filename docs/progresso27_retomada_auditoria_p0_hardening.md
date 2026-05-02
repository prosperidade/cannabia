# Progresso 27 — Retomada da auditoria, P0 hardening e fila da proxima passada

**Data:** 2026-05-01
**Branch:** `main`
**Contexto:** retomada apos sessao travada durante/apos aplicacao da migration 042
**Suite nesta retomada:** nao rodada completa; validado runner de migrations e estado do banco local

## 1. Objetivo desta entrada

Esta entrada reconstrui o estado real da auditoria apos a sessao anterior ter ficado travada por horas. O ponto principal: a documentacao de progresso parou em `docs/progresso26_c6_auto_ingest_atendimento.md`, mas o codigo ja avancou varios commits depois dela.

O objetivo aqui e alinhar a memoria operacional para encerrar a sessao com um handoff limpo: o que ja foi feito, o que foi validado agora, e o que deve abrir a proxima passada.

## 2. Estado do workspace na retomada

`git diff` nao mostrou alteracoes em arquivos rastreados. Havia apenas arquivos nao rastreados, aparentemente artefatos antigos de redesign:

- `.claude/scheduled_tasks.lock`
- `docs/Login.jsx`
- `docs/Login Redesign.html`
- `docs/Dashboard Redesign.html`

Esses arquivos nao foram incluidos nesta entrada nem no commit de handoff. Devem ser classificados depois como:

1. artefatos uteis de referencia visual;
2. material para commit separado de docs/design;
3. lixo local a remover apos confirmacao.

## 3. Commits posteriores ao progresso 26

Depois de `5def223 docs(progresso26): narrativa C6 fechada`, o historico de `main` ja contem:

| Commit | Entrega |
|---|---|
| `8891c97` | App paciente: envelope correto + telas `/p/consultas` e `/p/documentos` |
| `ea4cc42` | `/org/dashboard` com dados reais + lista de pacientes em acompanhamento ativo |
| `ed82aa7` | C7: agregacao clinica anonimizada via `knowledge_catalog` |
| `f706e3c` | P0 hardening: portal do paciente, integracoes, flags, permissao e migration 042 |
| `dd3bccb` | P0 hardening: exigir assinatura em webhooks WhatsApp em producao |

Isso torna desatualizada a tabela final do progresso 26. Itens que ainda estavam marcados como pendentes foram fechados no codigo.

## 4. Reconciliacao do roadmap

### 4.1. Concluido desde o progresso 26

- **App paciente**: telas `/p/consultas` e `/p/documentos`, ajuste de envelope do endpoint `/patient/profile`, expansao dos testes de `patient_portal`.
- **`/org/dashboard` real**: dados operacionais reais no lugar de parte dos mocks.
- **`/org/acompanhamento` ativo**: lista real de pacientes em acompanhamento ativo.
- **C7**: pipeline de agregacao clinica anonimizada, migration 041, rota admin e testes.
- **P0 hardening**:
  - migration 042 para honestidade do app paciente;
  - reducao de placeholders no portal;
  - seguranca de webhooks de pagamento/telemetria/WhatsApp;
  - system flags;
  - ajustes de permissao e configuracao.

### 4.2. Ainda pendente

- **P5 — ultima passada nos agentes IA**: refatorar agentes um por um, agora com o produto mais estavel.
- **Classificar artefatos de redesign nao rastreados** em `docs/`.
- **Rodar validacao pesada antes de abrir P5**, incluindo testes focados e suite completa.
- **Aplicar migrations 041/042 em qualquer ambiente que nao seja o banco local Docker**, se ainda nao tiver sido feito.
- **Pendencias operacionais antigas** permanecem fora desta sprint:
  - Polygon Amoy + caminho multi-sig/mainnet;
  - farmacovigilancia ANVISA real;
  - credenciais oficiais VigiMed/Notivisa;
  - encriptacao/rotacao operacional de `tenant_secrets` antes de PROD.

## 5. Validacoes feitas nesta retomada

### 5.1. Migration 042

Foi confirmado no banco local configurado no `.env` (`DATABASE_URL` apontando para Postgres Docker na porta 5434) que:

- `schema_migrations` contem `041_knowledge_case_aggregates.sql`;
- `schema_migrations` contem `042_patient_app_honesty.sql`;
- `appointments.doctor_id` existe;
- `appointments.appointment_type` existe;
- `treatment_plans.duration_days` existe;
- `treatment_plans.bottle_capacity_ml` existe;
- `treatment_plans.bottle_consumed_ml` existe.

Tambem foi executado:

```powershell
env\Scripts\python scripts\run_migrations.py
```

Resultado: nenhuma migration nova pendente; 001-042 foram puladas como ja aplicadas.

### 5.2. Suite

A suite completa nao foi rodada nesta retomada. A proxima passada deve comecar por validacao focada antes de qualquer refatoracao nova.

## 6. Proxima passada recomendada

Ordem recomendada para abrir a proxima sessao:

1. Rodar testes focados de seguranca, portal, migrations e knowledge:

```powershell
env\Scripts\pytest tests\test_patient_portal.py tests\test_migration_042_patient_app_honesty.py tests\test_case_aggregator.py tests\test_admin_case_aggregates.py tests\test_realtime_webhook_security.py tests\test_payments_webhook_security.py tests\test_system_flags.py -q
```

2. Rodar suite completa:

```powershell
env\Scripts\pytest -q
```

3. Decidir destino dos arquivos nao rastreados de redesign.

4. Abrir **P5 — ultima passada nos agentes IA**, na ordem:

| Ordem | Alvo | Motivo |
|---|---|---|
| 1 | `AgenteCientifico` | ja recebeu C6/C7; maior acoplamento com RAG e knowledge |
| 2 | `AgenteTratamento` | contrato clinico central para dosagem/plano |
| 3 | `AgenteAnamnese` | entrada do fluxo clinico e qualidade do contexto |
| 4 | `AgenteRegulatorio` | ponte com SCC, compliance e farmacovigilancia |
| 5 | Orquestradores (`clinical_flow`, services e rotas) | ajustar apos os agentes estabilizarem |

## 7. Criterio de pronto da proxima passada

- Suite focada verde.
- Suite completa verde ou falhas conhecidas documentadas.
- Artefatos nao rastreados classificados.
- Primeiro agente da P5 refatorado com testes.
- Novo progresso `docs/progresso28_*.md` registrando a passada.

