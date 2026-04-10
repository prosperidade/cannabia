# Progresso 7 — Backend Completo + Arquitetura de Agentes IA

## Data
2026-04-09

## Objetivo do dia
1. Auditoria completa backend vs frontend — identificar todos os gaps
2. Eliminar TODOS os endpoints mock — conectar ao PostgreSQL real
3. Criar endpoints faltantes para as 48 paginas do frontend
4. Planejar nova arquitetura de agentes IA (inspirada no Amigao do Meio Ambiente)
5. Planejar integracao MemPalace + Google Files API

---

## Trabalho realizado

### Fase 1 — Auditoria e Diagnostico

**Auditoria Frontend (48 rotas):**
- 32 paginas ja conectadas ao backend
- 6 paginas estaticas (redirects)
- 9 paginas com dados mock hardcoded no frontend
- 1 pagina UI pura (med/onboarding)

**Auditoria Backend (endpoints):**
- 13 endpoints retornavam dados mock (fallback hardcoded)
- 6 endpoints faltavam completamente
- Migrations com numeracao duplicada (dois 012)
- INSERTs referenciando tabelas inexistentes

**Auditoria AI Layer (14 arquivos, 3.463 linhas):**
- Pipeline monolitico de 3 estagios (Clinical > Treatment > Report)
- Orquestrador em service.py (CannabIAService)
- Dual-LLM: OpenAI GPT-4o-mini + Gemini 1.5 Flash com circuit breaker
- Guardrails: 4 camadas (regex, Unicode, LLM classifier, output validation)
- Prescriber: Rules engine + LLM + Safety clamp (medical-grade)
- RAG: ChromaDB + Google embeddings (gemini-embedding-001)
- Prompts: 7 prompts versionados com registry DB-backed
- Schemas: 30+ modelos Pydantic com function_calling

### Fase 2 — Correcao de Migrations

- Renomeado `012_telemetry_timeseries.sql` > `013_telemetry_timeseries.sql`
- Renomeado `013_missing_tables_and_columns.sql` > `014_missing_tables_and_columns.sql`
- Corrigido INSERT em 012 (`migration_log` > `schema_migrations`)
- Corrigido INSERT em 013 (`migration_tracking` > `schema_migrations`)
- Criada migration 015 (`users_enhancement.sql`: email, full_name, updated_at)
- Total: 16 migrations sequenciais (000-015) sem conflitos

### Fase 3 — Endpoints Mock > Real (13 endpoints)

**Patient Portal (5 endpoints):**
- GET /patient/profile — agora consulta treatment_plans para treatment_phase, current_dosage
- GET /patient/treatment — retorna plano real ou resposta vazia
- POST /patient/diary — retorna erro 500 no fallback (nao mock)
- GET /patient/diary — retorna lista vazia no fallback
- GET /patient/evolution — retorna metricas zeradas no fallback

**Org Management (8 endpoints):**
- GET /org/dashboard — integrou revenue real da tabela billing + chart revenue_by_month
- GET /org/patients — lista real paginada
- GET /org/doctors — removido guard `if doctors:`, retorna lista vazia se nao houver
- GET /org/stock — lista real do stock_inventory
- POST /org/stock/entry — erro 500 no fallback
- POST /org/stock/dispensation — erro 500 no fallback
- GET /org/billing — lista real com totais calculados
- GET /org/financial — valores reais da tabela billing

**Returns (1 endpoint):**
- GET /returns — query real em treatment_plans + patients

### Fase 4 — Endpoints Novos (11 endpoints)

**Admin Users (3):**
- GET /api/v1/admin/users/ — listagem com search/role + clinics memberships
- POST /api/v1/admin/users/ — criacao com bcrypt + vinculo clinica
- PATCH /api/v1/admin/users/<id> — atualizacao parcial

**Clinic Config (2):**
- GET /api/v1/org/config — dados da clinica + branding
- PATCH /api/v1/org/config — atualizacao de nome

**Reports BI (1):**
- GET /api/v1/org/reports?period=6m — agregacoes por mes (attendance, financial, patients, AI)

**Compliance ANVISA (1):**
- GET /api/v1/org/compliance — checklist dinamico com score (5 checks reais)

**Clinical Intelligence (4):**
- GET /api/v1/clinical/intelligence — dashboard IA (stats, by_model, executions, conditions)
- GET /api/v1/clinical/botanical — padroes de prescricao, ratios, evidencias
- GET /api/v1/clinical/lab?patient_id=N — analise laboratorial por paciente
- GET /api/v1/clinical/trials — outcomes de tratamento agregados

### Fase 5 — Frontend Conectado ao Backend (10 paginas)

- /admin (dashboard KPIs reais via getAdminStats)
- /admin/usuarios (listAdminUsers + createAdminUser)
- /org/campanhas (listCampaignTemplates + listCampaignExecutions)
- /org/config (getClinicConfig + updateClinicConfig)
- /org/relatorios (getOrgReports com period)
- /org/compliance (getOrgCompliance)
- /med/inteligencia (getClinicalIntelligence)
- /med/botanical (getBotanicalAnalysis)
- /med/lab-ai (getLabAnalysis)
- /med/ensaios (getClinicalTrials)

### Fase 6 — Seeds e Validacao

- Corrigido user_id hardcoded nos seeds (2 > 6 medico, 2 > 7 atendente, 4 > 8 paciente)
- Seed completo: ~200 registros em todas as tabelas
- Setup local executado com sucesso (16 migrations + seeds)
- Todos os 71 endpoints testados via curl com dados reais do PostgreSQL

---

## Metricas Finais

| Metrica | Antes | Depois |
|---------|-------|--------|
| Endpoints API v1 | ~57 | **71** |
| Paginas frontend com backend real | 32/48 | **41/48** |
| Paginas estaticas (OK) | 6/48 | **6/48** |
| Paginas com mock | 9/48 | **1/48** (med/onboarding, UI pura) |
| TypeScript errors | 0 | **0** |
| Tabelas PostgreSQL com seed | ~25 | **39** |
| Blueprints Flask registrados | 16 | **20** |

---

## Decisoes Registradas

### Decisao 1: Google Files API para legislacao (ANVISA/CFM)
- **O que**: Abandonar chunks/RAG para documentos regulatorios, usar Google API com arquivo completo
- **Por que**: Legislacao e auto-referenciada (artigos citam outros artigos). Chunks cortam contexto.
- **Abordagem**: Hibrida — Google API para legislacao, ChromaDB mantido para artigos cientificos
- **Impacto**: Precisao regulatoria ~70% > ~95%, manutencao reduzida

### Decisao 2: MemPalace para memoria de agentes
- **O que**: Instalar MemPalace 3.0 para memoria persistente entre sessoes
- **Por que**: Pipeline atual comeca do zero a cada execucao. Nao acumula conhecimento.
- **Abordagem**: Wing `cannabia_clinical` com 10 rooms + filtro LGPD obrigatorio
- **Impacto**: Startup 170 tokens vs ~3k, custo mensal ~$12-20 vs ~$45-80
- **Cuidado LGPD**: NUNCA armazenar PII no palace. Apenas padroes anonimizados e agregados.

### Decisao 3: Refatorar pipeline monolitico para arquitetura de agentes
- **O que**: Quebrar CannabIAPipeline (monolitico) em agentes independentes com BaseAgent
- **Por que**: Permite memoria por agente, chains configuráveis, skills modulares
- **Referencia**: Arquitetura do Amigao do Meio Ambiente (10 agentes + orchestrator)
- **Agentes planejados**: anamnese, prescritor, cientifico, regulatorio, triagem, follow-up

---

## Analise do AI Layer Atual vs Arquitetura de Agentes

### Estado atual (monolitico)
```
CannabIAService.process_patient_case()
  > Billing check
  > Guardrails validation
  > CannabIAPipeline.run()
      > Stage 1: run_clinical_analysis() [OpenAI]
      > Stage 2: run_treatment_plan() [OpenAI]
      > RAG lookup [ChromaDB]
      > Stage 3: run_scientific_report_rag() [Gemini] ou run_scientific_report() [OpenAI]
  > Cost calculation
  > Audit logging
```

**Problemas:**
1. Pipeline rigido — nao da para executar Stage 2 sem Stage 1
2. Sem memoria entre execucoes — cada caso comeca do zero
3. Prescritor desconectado do pipeline — chamado separadamente
4. Triagem (triage agent) desconectada — tem schemas mas nao integra no fluxo
5. Sem skills/tools modulares — logica embedada nos chains

### Arquitetura alvo (agentes)
```
Orchestrator
  > AgenteTriagem (WhatsApp/Chat > widgets > extracao de condicoes)
  > AgenteAnamnese (analise clinica estruturada)
  > AgentePrescritor (rules engine + LLM + safety clamp)
  > AgenteCientifico (RAG artigos + Google Files API legislacao)
  > AgenteRegulatorio (ANVISA/CFM compliance check)
  > AgenteFollowUp (CRM, diary, telemetria)
  
Cada agente:
  - Herda de BaseAgent
  - Tem palace_room no MemPalace
  - Tem recall_memory() e remember()
  - Tem skills registradas
  - Tem diary automatico
```

### Skills por agente planejadas

| Agente | Skills |
|--------|--------|
| AgenteTriagem | extract_conditions, detect_red_flags, select_widget, schedule_appointment |
| AgenteAnamnese | analyze_symptoms, assess_risk_level, recommend_exams, identify_comorbidities |
| AgentePrescritor | calculate_dosage, check_interactions, generate_titration, clamp_safety |
| AgenteCientifico | search_pubmed, search_cochrane, cite_evidence, summarize_study |
| AgenteRegulatorio | check_anvisa_compliance, verify_prescription_legal, check_cfm_norms |
| AgenteFollowUp | schedule_return, analyze_diary, correlate_symptoms, adjust_dosage |

---

## Proximos Passos — Sprints de Implementacao

### Sprint 1: Google Files API para Legislacao (2 dias)
- Criar modulo `src/knowledge/google_files.py`
- Upload documentos regulatorios (RDC 327, RDC 660, Lei 11.343, resolucoes CFM)
- Endpoint `GET /api/v1/regulatory/query`
- Coexistencia com ChromaDB (artigos cientificos)

### Sprint 2: MemPalace (1 dia)
- Instalar mempalace>=3.0.0
- Criar mempalace.yaml (wing cannabia_clinical, 10 rooms)
- Criar src/ai/memory.py (helper fire-and-forget)
- Volume persistente Docker/Render
- Filtro LGPD (sanitizer de PII)

### Sprint 3: BaseAgent + Agentes (3 dias)
- Criar src/ai/agents/base.py (BaseAgent com palace_room, recall, remember)
- Criar 6 agentes (triagem, anamnese, prescritor, cientifico, regulatorio, follow_up)
- Criar src/ai/agents/orchestrator.py (chain manager)
- Migrar logica existente (pipeline.py, prescriber.py) para agentes
- Manter backward compatibility com CannabIAService

### Sprint 4: Integracao + Validacao (1 dia)
- Testar pipeline completo com agentes
- Verificar LGPD (nenhum PII no palace)
- Benchmark: custo e precisao antes/depois
- Documentar arquitetura final

---

## Arquivos relevantes do dia

### Criados
| Arquivo | Funcao |
|---------|--------|
| src/web/routes/admin_users.py | CRUD de usuarios para /admin/usuarios |
| src/web/routes/clinic_config.py | Config da clinica GET/PATCH |
| src/web/routes/reports.py | BI reports agregados |
| src/web/routes/compliance.py | Checklist ANVISA dinamico |
| src/web/routes/clinical_intelligence.py | 4 endpoints clinicos avancados |
| migrations/015_users_enhancement.sql | email, full_name, updated_at em users |

### Modificados
| Arquivo | Mudanca |
|---------|---------|
| src/web/routes/patient_portal.py | Mock > real queries + empty fallback |
| src/web/routes/org_management.py | Mock > real queries + billing integration |
| src/web/routes/returns.py | Mock > real queries |
| src/app.py | 4 novos blueprints registrados |
| frontend/lib/api.ts | 20+ novas funcoes de API |
| frontend/app/admin/usuarios/page.tsx | Mock > listAdminUsers() + createAdminUser() |
| frontend/app/org/campanhas/page.tsx | Mock > listCampaignTemplates() + executions |
| frontend/app/admin/page.tsx | Mock KPIs > getAdminStats() |
| frontend/app/med/inteligencia/page.tsx | Mock > getClinicalIntelligence() |
| frontend/app/med/botanical/page.tsx | Mock > getBotanicalAnalysis() |
| frontend/app/med/lab-ai/page.tsx | Mock > getLabAnalysis() |
| frontend/app/med/ensaios/page.tsx | Mock > getClinicalTrials() |
| frontend/app/org/config/page.tsx | Mock > getClinicConfig() |
| frontend/app/org/relatorios/page.tsx | Mock > getOrgReports() |
| frontend/app/org/compliance/page.tsx | Mock > getOrgCompliance() |
| scripts/seed_comprehensive.py | Corrigido user_ids + seed stock_dispensations |
| migrations/012_prescriptions_orders.sql | Fix INSERT schema_migrations |
| migrations/013_telemetry_timeseries.sql | Renomeado + fix INSERT |
| migrations/014_missing_tables_and_columns.sql | Renomeado + adicionado tracking |
| .env | DATABASE_URL local corrigido |
