# BACKLOG — Sandbox Compliance Core (SCC)

## 1. Propósito

Este documento consolida o backlog priorizado de implementação do **Sandbox Compliance Core (SCC)** da CannabIA, materializando a série regulatória `docs/23` a `docs/27` em sequência executável.

O backlog é complementar a `docs/22_EXECUTIVE_BACKLOG.md` (Frente I), fornecendo granularidade adicional de tarefas, dependências e decisões humanas pendentes.

**Base de leitura recomendada antes de trabalhar neste backlog:**

- `docs/23_SANDBOX_COMPLIANCE_CORE.md` — desenho arquitetural completo
- `docs/24_PILOT_PROGRAM_AND_INSTITUTIONAL_PARTNERSHIPS.md` — programa piloto
- `docs/25_SCC_DATA_MODEL_AND_MIGRATIONS.md` — modelagem física e DDL
- `docs/26_BLOCKCHAIN_ANCHORING_PROTOCOL.md` — protocolo de ancoragem
- `docs/27_REGULATORY_TEMPLATES_LIBRARY.md` — biblioteca de templates
- `HANDOFF_VALIDATION_REPORT.md` — relatório de validação (raiz do repositório)

---

## 2. Fases do backlog

### Fase 0 — Pré-requisitos (obrigatórios antes do SCC começar a escrever)

Nenhuma escrita no banco pelo SCC antes de sanear a base conforme `docs/progresso17_auditoria_completa_e_melhorias.md`, Prioridade 1.

| ID | Tarefa | Prioridade | Responsável sugerido | Status |
|----|--------|-----------|----------------------|--------|
| P0.1 | Migration `022_integrity_hardening.sql` — UNIQUE em `users.email`, UNIQUE em `triage_links.token_hash`, FK em `patients.user_id`, CHECK em `patients.status`/`treatment_plans.status`/`anamnesis_reports.status`, GIN em `ai_audit_logs.input_payload`/`output_payload` | Alta | Backend | **SQL pronto, pendente aplicação** (arquivo escrito em 2026-04-19 + 30 testes estáticos; aplicar via `scripts/setup_local.py`) |
| P0.2 | Migration `023_timestamp_standardization.sql` — padronizar `TIMESTAMP → TIMESTAMPTZ` nas tabelas criadas pelas migrations `001` e `003` | Alta | Backend | **SQL pronto, pendente aplicação** (arquivo escrito em 2026-04-19; aplicação em loop sobre `TEXT[][]` com guards em `information_schema`) |
| P0.3 | `.github/workflows/ci.yml` — `pytest -q` + `tsc --noEmit` em todo PR | Alta | Backend | **Concluído** 2026-04-19 — dois jobs (backend com `postgres:16-alpine` + frontend node 20), concurrency group cancela builds superados |
| P0.4 | `.env.example` completo — `DEFAULT_CLINIC_ID`, `TELEMETRY_*`, `PAYMENT_WEBHOOK_SECRET_*` | Média | Backend | **Concluído** 2026-04-19 — 17 chaves adicionais documentadas por categoria (DB_POOL_*, FLASK_ENV, OPENAI_TIMEOUT, GEMINI_*, TASK_*, REDIS_URL, PUBMED_EMAIL, frontend Next.js) |
| P0.5 | Política formal de backup/DR + scripts `migrations/down/` para rollback | Média | Ops | **Concluído** 2026-04-19 — `docs/BACKUP_AND_DISASTER_RECOVERY.md` + `migrations/down/` (README + down scripts 022 e 023). Primeiro teste trimestral de recuperação agendado até 2026-05-19 |

---

### Fase 1 — Fundação do SCC (Governance Hub + Tenants tipados)

Entregar o cadastro institucional completo e a discriminação formal de tenant type. A partir daqui, uma associação pode se cadastrar e ter sua elegibilidade validada automaticamente.

| ID | Tarefa | Dependência | Prioridade | Status |
|----|--------|-------------|-----------|--------|
| F1.1 | Migration `024_tenants_evolution.sql` — introduzir discriminador `tenant_type` (clinic/association/doctor), adicionar campos estatutários, migrar `clinics` com `clinic_id = tenant_id` | P0.1, P0.2 | Alta | **Concluído** 2026-04-19 — 7 colunas adicionadas (`tenant_type` VARCHAR CHECK, `trade_name`, `cnpj` UNIQUE partial, `incorporation_date`, `plan_tier` VARCHAR CHECK com mapeamento starter→basic, `whitelabel_config` JSONB, `is_active` GENERATED). 38 testes estáticos verdes + down script validado em roundtrip. Migração do FK `clinic_id = tenant_id` nos child tables fica para migrations subsequentes (F1.2+) |
| F1.2 | Migration `025_governance_schema.sql` — `associations`, `technical_responsibles`, `board_members`, `institutional_documents`, `capability_matrix` | F1.1 | Alta | Aberto |
| F1.3 | Repositório `src/repositories/governance_repository.py` | F1.2 | Alta | Aberto |
| F1.4 | Serviço `src/services/governance_service.py` — validação de elegibilidade (natureza jurídica, tempo de constituição, RT habilitado) | F1.3 | Alta | Aberto |
| F1.5 | Blueprint `src/web/routes/governance.py` — endpoints de cadastro, atualização e geração de Dossiê de Elegibilidade | F1.4 | Alta | Aberto |
| F1.6 | Extensão `src/ai/agents/regulatorio.py` — skill `check_sandbox_eligibility(association)` | F1.4 | Alta | Aberto |
| F1.7 | Frontend `frontend/app/org/sandbox/governance/page.tsx` — cadastro institucional e visualização do Dossiê | F1.5 | Média | Aberto |
| F1.8 | Testes `tests/test_governance.py` — elegibilidade, documentos, RT | F1.5 | Alta | Aberto |

---

### Fase 2 — Member Registry + Base de Rastreabilidade

| ID | Tarefa | Dependência | Prioridade | Status |
|----|--------|-------------|-----------|--------|
| F2.1 | Migration `026_members_schema.sql` — `association_members`, `membership_status_history`, `informed_consents`, extensão de `patients` com FK opcional a `association_members` | F1.1 | Alta | Aberto |
| F2.2 | Migration `027_quality_schema.sql` — `sops`, `sop_versions`, `sop_trainings`, `sop_evidences`, `sop_deviations`, `capa_actions` | F1.1 | Média | Aberto |
| F2.3 | Migration `028_traceability_schema_base.sql` — `seed_lots`, `genetic_matrices`, `plants`, `cultivation_batches`, `harvests`, `extractions`, `api_vegetables`, `preparations`, `dispensations`, `lab_analyses` | F1.1 | Alta | Aberto |
| F2.4 | Migration `029_traceability_hash_chaining.sql` — `traceability_events` com `event_hash`, `previous_hash`, `chain_id`, `chain_sequence` | F2.3 | Alta | Aberto |
| F2.5 | Migration `030_traceability_triggers.sql` — triggers append-only + validação de cadeia no INSERT + revogação de UPDATE/DELETE | F2.4 | Alta | Aberto |
| F2.6 | Repositório e serviço `src/repositories/traceability_repository.py` + `src/services/traceability_service.py` | F2.5 | Alta | Aberto |
| F2.7 | Blueprint `src/web/routes/traceability.py` — registro e consulta de eventos, leitura por QR Code | F2.6 | Alta | Aberto |
| F2.8 | Repositório/serviço SOPs com versionamento, assinatura eletrônica e evidências automáticas | F2.2 | Média | Aberto |
| F2.9 | Testes `tests/test_traceability.py` — hash chaining, detecção de reescrita retroativa, integridade de cadeia | F2.7 | Alta | Aberto |

---

### Fase 3 — Farmacovigilância e Reporting

| ID | Tarefa | Dependência | Prioridade | Status |
|----|--------|-------------|-----------|--------|
| F3.1 | Migration `031_pharmacovigilance_schema.sql` — `sanitary_risks`, `risk_controls`, `adverse_events`, `pharmacovigilance_notifications` | F1.1 | Alta | Aberto |
| F3.2 | Migration `032_regulatory_schema.sql` — `sandbox_projects`, `sandbox_protocols`, `sandbox_indicators`, `sandbox_submissions`, `regulatory_reports` | F1.1 | Alta | Aberto |
| F3.3 | Captura estruturada de eventos adversos via WhatsApp/web/consulta — serviço `src/services/adverse_event_service.py` | F3.1 | Alta | **Concluído** 2026-04-24 — `adverse_event_service.py` (7 funções: `capture_adverse_event`, `get_event`, `list_events`, `count_by_severity`, `record_triage_result`, `set_clinical_assessment`, `set_outcome`; dataclass imutável `AdverseEvent` com property `requires_regulatory_notification` derivada da whitelist `NOTIFIABLE_SEVERITIES = {severe, life_threatening, fatal}` — gancho pronto para F3.5) + `adverse_event_repository.py` (INSERT + SELECT + 3 UPDATEs com RETURNING, escopados por tenant_id). Validações: whitelists `severity`/`reported_via`/`outcome` espelhando CHECKs da migration 031, ordem temporal `event_onset_at <= reported_at`, descrição não vazia, dict JSONB para triagem IA. 33 testes (10 validação pura sem DB + 23 integração contra Postgres real cobrindo captura minimal, captura com membro+onset, strip de descrição, get roundtrip, isolamento cross-tenant, filtros severity/reported_via/member/has_triage/janela, count_by_severity, ordenação DESC, updates de triagem/parecer/outcome, parametrização da property notifiable). |
| F3.4 | Extensão `src/ai/agents/regulatorio.py` — skill `triage_adverse_event(report)` com classificação de severidade | F3.1 | Alta | **Concluído** 2026-04-24 — skill deterministica (heuristica regex PT-BR, sem LLM) registrada em `AgenteRegulatorio._triage_adverse_event`. Escala a severidade reportada via `max(rank_reportado, max(ranks_das_keywords_batidas))` sobre padrões organizados em 4 níveis (moderate/severe/life_threatening/fatal); nunca baixa a severidade reportada. Output versionado em `TRIAGE_MODEL_VERSION="regulatorio-triage-v1-heuristic"` para auditabilidade cross-versão quando substituido por modelo IA. Retorna `{severity_reported, severity_suggested, escalated, notify_required, red_flags, matched_by_level, reasoning, model_version}`. Persistência opt-in via `persist=True` + `event_id` + `tenant_id` chama `adverse_event_service.record_triage_result`. Aceita `report` como dict ou objeto com atributos (compat com dataclass `AdverseEvent`). Whitelist `_TRIAGE_NOTIFIABLE` duplicada deliberadamente do service para manter o agente testável sem DB. 13 testes (skill registrada, validações, não-escalação mild, escala a severe/life_threatening/fatal, não-downgrade, aceita objeto, persist com/sem ids, persist em evento inexistente). |
| F3.5 | Integração `src/integrations/vigimed.py` — notificação automatizada à ANVISA via VigiMed/Notivisa | F3.3 | Alta | **Concluído** 2026-04-24 — wrapper pure-integration com dispatcher por env `ANVISA_NOTIFICATION_PROVIDER` (valores `mock\|vigimed\|notivisa`). Arquitetura alinhada com F5.3 (`opentimestamps.py`) / F5.4 (`polygon_anchor.py`): protocolo `_NotificationClient`, `MockNotificationClient` deterministico (reference = SHA-256 do payload canonicalizado, prefix `MOCK-`), `_ProductionVigiMedClient` / `_ProductionNotivisaClient` como stubs com lazy import (levantam `VigiMedSubmissionError` até credenciais/lib oficial serem plugadas — ops). Saída `NotificationReceipt(notification_target, notification_reference, submitted_at, response_payload)` shape-estável para consumo da F3.6. Hierarquia de erros `PharmacovigilanceError` → `UnknownProviderError` / `VigiMedUnavailableError` / `VigiMedSubmissionError`. `build_notification_payload(event)` aceita dict ou dataclass `AdverseEvent` (compat com F3.3). Mapeamento provider→target: `mock`→`internal_only`, `vigimed`→`vigimed`, `notivisa`→`notivisa` (alinha com whitelist da migration 031). DELIBERADAMENTE não persiste — gravação em `pharmacovigilance_notifications` fica para F3.6. 32 testes (contratos, resolve_provider com cascata arg>env>default, payload builder, determinismo do mock, 3 mapeamentos de target, dispatcher com env, override explícito, injection de client, validações, hierarquia de erros, smoke com dataclass real). |
| F3.6 | Blueprint `src/web/routes/pharmacovigilance.py` — captura, triagem, notificação e dashboard epidemiológico | F3.3, F3.5 | Alta | **Concluído** 2026-04-25 — costura completa F3.3+F3.4+F3.5 + persistência em `pharmacovigilance_notifications`. Camadas: (a) `pharmacovigilance_notification_repository.py` (insert/get/list_for_event/count_for_tenant/record_response com escopagem por tenant via JOIN com `adverse_events.tenant_id` — `_COLUMNS_N` qualificado para evitar ambiguidade de `id`); (b) `pharmacovigilance_service.py` orquestrador com 3 casos de uso (`triage_event` → invoca skill F3.4 com `persist=True`; `notify_event` → submete via `vigimed.submit_notification` e grava receipt em pharmacovigilance_notifications; `dashboard_summary` → `count_by_severity` + `notifications_by_target`) + erros tipados `AdverseEventNotFoundError` para mapping HTTP estável; (c) blueprint `pharmacovigilance.py` com 8 rotas `/api/v1/pharmacovigilance/*`: POST/GET `/adverse-events`, GET `/<id>`, PUT `/<id>/clinical-assessment`, PUT `/<id>/outcome`, POST `/<id>/triage`, POST `/<id>/notify`, GET `/<id>/notifications`, GET `/dashboard`. Mapping HTTP: not_found→404, validation_error→422, unknown_provider→422, notification_failed→502. Auth padrão `@api_role_required("Admin", "Medico")` + CSRF nos writes (idêntico ao governance/compliance). Webhook do WhatsApp continua chamando `adverse_event_service.capture_adverse_event` direto (não passa pelo blueprint, conforme decidido). Blueprint registrado em `src/app.py`. 45 testes (14 service contra Postgres real + 31 blueprint com mocks via monkeypatch). Suite: 1357 → 1402 passed. |
| F3.7 | Blueprint `src/web/routes/regulatory_reporting.py` — dashboards ANVISA-ready com indicadores calculados em tempo real | F3.2 | Alta | **Concluído** 2026-04-25 — read-only (sem service intermediário, igual `compliance.py`). Camadas: (a) `regulatory_reporting_repository.py` cobrindo as 6 tabelas de migration 032 + view `v_sandbox_indicator_dashboard` (F6.2): `list_projects/get_project/count_projects_by_status` em sandbox_projects; `get_active_protocol` (preferindo `effective_until IS NULL`, fallback no `effective_from` mais recente); `list_indicator_dashboard/get_indicator_dashboard_row/list_indicator_history/count_indicators_status` na view + sandbox_indicator_values (escopagem por JOIN com sandbox_projects); `list_submissions/count_submissions_pending` em regulatory_submissions; `list_reports/count_reports_by_type` em regulatory_reports; (b) blueprint `regulatory_reporting.py` em `/api/v1/regulatory-reporting/*` com 7 rotas read-only (GET): `/projects`, `/projects/<id>`, `/indicators`, `/indicators/<id>`, `/submissions`, `/reports`, `/overview`. Funções puras `compute_indicators_score` (% mandatórios `on_target`) e `compute_overview` (KPIs top-level: total/active_or_pending de projetos, score de indicators, awaiting_anvisa_response, total de reports) testáveis sem DB. Whitelists `_PROJECT_STATUSES` e `_REPORT_TYPES` espelhando CHECKs da migration 032. Auth `@api_role_required("Admin", "Medico")`. Deliberadamente NÃO confunde com `regulatory.py` (legislation Google Files API) — prefixos distintos. 48 testes (25 repo contra Postgres real com fixture full setup tenant→project→protocol→indicator→values→submission→report; 23 blueprint mockados com escopo no parsing/validação/serialização + cálculo de overview). Suite: 1402 → 1450 passed. **Bug capturado**: view `v_sandbox_indicator_dashboard` define `on_target = abs(latest - target) / abs(target) <= 0.05` (tolerância de 5% — não "atingiu o alvo"); fixture original com 90 vs target 80 estava off_target; ajustado para 82 vs 80 (2.5%). |
| F3.8 | Testes `tests/test_pharmacovigilance.py` | F3.6 | Alta | Aberto |

---

### Fase 4 — Evidence Engine e Templates

| ID | Tarefa | Dependência | Prioridade | Status |
|----|--------|-------------|-----------|--------|
| F4.1 | Serviço `src/services/evidence_service.py` — agregação longitudinal por condição clínica, correlação dose-efeito, extração de desfechos da telemetria pós-consulta (D+3/D+7/D+15 já existente) | F2.5 | Média | **Concluído** 2026-04-23 — `evidence_service.py` (5 funções públicas + 4 dataclasses + classify_response_text deterministico keyword-based PT-BR) + `evidence_repository.py` (queries pre-agregadas em scheduled_followups/symptom_diary/treatment_plans). 31 testes (21 unit do classifier + 10 integration contra Postgres real). Confirmado que a "dependência F2.5 outcome capture" do progresso21 era ilusória — a telemetria existente já fornece outcomes longitudinais. |
| F4.2 | Geração de estudos observacionais internos com metodologia reprodutível | F4.1 | Baixa | **Concluído** 2026-04-23 — provider `build_observational_study_data` em `regulatory_documents.py` + template `observational_studies/cohort_study_v1.md.j2` (9 seções: identificação, resumo executivo, metodologia, cohort pooled, dose-efeito, follow-ups, sample qualitativo, limitações, reprodutibilidade). Categoria nova `observational_studies` no registry. Sample anonimizado (só patient_id, sem nomes). `study_id` deterministico. `EVIDENCE_ENGINE_VERSION` gravado na metodologia para auditoria. 12 testes (shape, anonimização, reprodutibilidade do study_id, registry resolve, render minimal/com dados, determinismo do content_hash dado estado estável). |
| F4.3 | Estrutura `data/templates/` conforme `docs/27_REGULATORY_TEMPLATES_LIBRARY.md` — `registry.yaml` + templates Jinja2 | Independente | Média | Aberto |
| F4.4 | Engine de geração de documentos `src/services/template_engine.py` — merge template + dados + configuração com versionamento | F4.3 | Média | Aberto |
| F4.5 | Redação dos 5 planos obrigatórios do Projeto Experimental (Jinja2) | F4.4 | Alta | Aberto |
| F4.6 | Redação do Dossiê de Elegibilidade, Parecer Final e documentos complementares | F4.4 | Alta | Aberto |
| F4.7 | Fluxo de aprovação bilateral — revisão pelo RT, revisão jurídica parceira (opcional), assinatura eletrônica | F4.4 | Média | Aberto |

---

### Fase 5 — Imutabilidade e Ancoragem

| ID | Tarefa | Dependência | Prioridade | Status |
|----|--------|-------------|-----------|--------|
| F5.1 | Migration `033_crypto_schema.sql` — `blockchain_anchors`, `anchor_coverage` | F1.1 | Média | Aberto |
| F5.2 | Serviço `src/services/anchoring_service.py` — cálculo de raiz Merkle diária, submissão a OpenTimestamps (Bitcoin), registro em smart contract Polygon | F5.1 | Média | Aberto |
| F5.3 | Integração `src/integrations/opentimestamps.py` | F5.2 | Média | Aberto |
| F5.4 | Smart contract Polygon — deploy do contrato de registro de raízes Merkle | F5.2 | Média | Aberto |
| F5.5 | Interface pública de verificação — endpoint `GET /public/anchors/<tenant_id>/verify?event_id=...` com Merkle proof | F5.2 | Média | Aberto |
| F5.6 | Testes `tests/test_anchoring.py` — cálculo de raiz, geração de proof, verificação | F5.2 | Média | Aberto |
| F5.7 | Runbook de operação — cadência, retry, reorgs, fallbacks | F5.2 | Baixa | Aberto |

---

### Fase 6 — Observabilidade, Índices e Seeds

| ID | Tarefa | Dependência | Prioridade | Status |
|----|--------|-------------|-----------|--------|
| F6.1 | Migration `034_indexes_and_performance.sql` — índices compostos críticos para rastreabilidade, farmacovigilância e auditoria | F2.5, F3.1 | Média | **Concluído** 2026-04-23 — escrita como `035_indexes_and_performance.sql` (slot 034 já consumido por review_workflows na sessão de 2026-04-21). 11 índices compostos: 2 em traceability_events (cobre doc 25 §13.2), 2 em adverse_events (cobre §13.2 + filtro por severity), 1 partial em pharmacovigilance_notifications (pendentes), 1 partial em scheduled_followups (responded — hot path do F4.1), 1 em treatment_plans (clinic+status+created), 1 em ai_audit_logs (time-series), 1 partial em blockchain_anchors (pending — anchor_upgrade), 1 em sandbox_indicator_values (latest), 1 em symptom_diary (tenant scope). 36 testes (12 static + 24 integration validando presença e shape dos partials). Roundtrip down/up validado. |
| F6.2 | Migration `035_views_and_helpers.sql` — views operacionais (dashboard ANVISA-ready, matriz de capacidade, trilha consolidada) | F6.1 | Média | **Concluído** 2026-04-23 — escrita como `036_views_and_helpers.sql` (slot 035 já consumido por indexes_and_performance). 3 views (`v_member_active_prescriptions` com cálculo de expiração via validity_days, `v_traceability_chain_status` com último hash da cadeia, `v_sandbox_indicator_dashboard` regular view com flag `on_target` em tolerância 5%) + 2 funções (`fn_generate_event_hash` SHA-256 sem pgcrypto + `fn_verify_chain_integrity` retorna TABLE com diagnóstico por sequence). Decisão: regular view (não materialized) para freshness — bump pra materialized + REFRESH cron quando volume justificar. 19 testes (4 static + 15 integration validando determinismo do hash, detecção de cadeia quebrada via bypass de trigger, agregação correta das views). |
| F6.3 | Migration `036_seed_data_sandbox.sql` — riscos sanitários padrão, categorias de SOP, templates de relatório | F6.2 | Baixa | **Concluído** 2026-04-23 — escrita como `037_seed_data_sandbox.sql` (slot 036 consumido por views_and_helpers). Catálogo como função opt-in `seed_sandbox_defaults(tenant_id)` — 10 sanitary_risks (contaminação, dosagem, farmacovigilância, rastreabilidade, LGPD, supply, regulatório, incluindo 2 critical que refletem invariantes do Art. 17) + 10 SOPs em 6 áreas (cultivation, extraction, quality_control, dispensation, pharmacovigilance, governance). Idempotente via ON CONFLICT DO NOTHING. Helper `seed_sandbox_defaults_all_associations()` popula só tenants 'association' sem catálogo ainda. Templates de relatório são file-based (data/templates/registry.yaml), fora do escopo de seed SQL. 14 testes. |
| F6.4 | Blueprint `src/web/routes/compliance.py` — evolução do checklist atual para agregador dos 7 submódulos do SCC | F3.7 | Média | **Concluído** 2026-04-23 — endpoint `GET /api/v1/org/compliance/overview` agrega os 7 submódulos (governance, members, quality, traceability, pharmacovigilance, regulatory, crypto) com score 0-100 por submódulo + overall_score (média simples) + checks detalhados. Endpoint `GET /compliance/submodule/<name>` retorna um submódulo só. Checklist legado em `/compliance` mantido intacto para retrocompat. 7 funções `<name>_summary(tenant_id)` testáveis isoladamente. Usa `v_member_active_prescriptions` e `v_sandbox_indicator_dashboard` da F6.2. 15 testes cobrindo estados vazios, dados populados e registry das 7. |

---

### Fase 7 — Piloto e Parcerias

Conforme `docs/24_PILOT_PROGRAM_AND_INSTITUTIONAL_PARTNERSHIPS.md`.

| ID | Tarefa | Dependência | Prioridade | Status |
|----|--------|-------------|-----------|--------|
| F7.1 | Formalização da carta de intenção com associação-piloto | Decisão humana | Alta | Planejado |
| F7.2 | Termo de participação com condições especiais de custo | F7.1 | Alta | Planejado |
| F7.3 | Acordo de compartilhamento de dados anonimizados | F7.1 | Alta | Planejado |
| F7.4 | Comitê de acompanhamento | F7.1 | Média | Planejado |
| F7.5 | Implantação completa do SCC no tenant da associação-piloto | F1–F6 | Alta | Planejado |
| F7.6 | Documentação contínua dos aprendizados e métricas | F7.5 | Alta | Planejado |
| F7.7 | Aproximação institucional com entidade nacional representativa | F7.6 | Média | Planejado |

---

## 3. Dependências externas

| Dependência | Momento de uso | Status |
|---|---|---|
| Publicação do Edital de Chamamento Público ANVISA | Parametriza F1.5, F3.2 e F4.5 | Aguardando ANVISA |
| Integração técnica SNGPC | F2.7 (quando aplicável) | Dependente de chave API ANVISA |
| Integração VigiMed/Notivisa | F3.5 | Dependente de credenciais oficiais |
| OpenTimestamps | F5.2 | Protocolo público, sem bloqueio |
| Polygon | F5.2 | Requer wallet + gas budget |
| Laboratórios de análise de canabinoides | F2.3 (lab_analyses) | Dependente de parcerias comerciais |
| Base Receita Federal / Portal Transparência | F1.4 (validação de CNPJ) | API pública disponível |

---

## 4. Decisões humanas pendentes

1. **Blueprint `compliance.py` — opção A vs. B.** Recomendação no `HANDOFF_VALIDATION_REPORT.md` é opção B (blueprints dedicados por submódulo + agregador).
2. **Precificação concreta do plano Sandbox Ready.** Fee recorrente + ticket por associado + setup. Documento comercial separado.
3. **Critérios de credenciamento da rede de escritórios parceiros.** Contratos-base, comissionamento, SLA.
4. **Associação-piloto.** Formalização bilateral.
5. **Política formal de retenção de dados regulatórios.** Tempo mínimo pós-encerramento do sandbox.
6. **Fornecedor de ancoragem em Polygon.** Smart contract próprio ou serviço de terceiros.
7. **Prioridade do SCC vs. backlog P1 do `progresso17`.** Confirmar sequenciamento estrito (P0 antes de F1) ou paralelismo controlado.
8. **Modelagem do SKU de consultoria parceira.** Cobrança direta pela CannabIA com repasse ou contratação direta pelo cliente com recomendação.
9. **Dados pessoais de membros do corpo diretivo.** Quais campos são PII sensível e devem ir para tabela de contexto apagável vs. tabela imutável.
10. **Escopo da integração com SNGPC.** Em que cenários exatos é aplicável para associações de pacientes.

---

## 5. Critérios de pronto por fase

### Fase 0 pronta quando

- Migrations `022` e `023` aplicadas em produção sem regressão
- CI rodando `pytest -q` e `tsc --noEmit` em todo PR
- `.env.example` completo validado por novo desenvolvedor onboarding

### Fase 1 pronta quando

- Uma associação consegue se cadastrar ponta a ponta, com validação automática de elegibilidade
- Dossiê de Elegibilidade é gerado automaticamente e submissível
- Testes de elegibilidade passam

### Fase 2 pronta quando

- Um lote de semente pode ser registrado, seguido por plantio, colheita, extração, produção e dispensação
- Qualquer alteração retroativa quebra a cadeia de hashes e é detectada
- Leitura de QR Code por fiscal retorna a trilha pública do evento
- Testes de integridade passam

### Fase 3 pronta quando

- Paciente consegue reportar evento adverso via WhatsApp
- IA triagem classifica severidade
- VigiMed/Notivisa recebe a notificação dentro do prazo regulatório
- Dashboard epidemiológico mostra dados reais

### Fase 4 pronta quando

- Os 5 planos obrigatórios são gerados automaticamente a partir dos dados do tenant
- Dossiê de Elegibilidade e Parecer Final são gerados automaticamente
- 90%+ dos campos são preenchidos automaticamente

### Fase 5 pronta quando

- Raiz Merkle diária é ancorada em Bitcoin (OTS) e Polygon
- Qualquer pessoa consegue verificar independentemente um evento via interface pública
- Nenhum PII toca a blockchain pública

### Fase 6 pronta quando

- `compliance.py` agrega os 7 submódulos como dashboard ANVISA-ready
- Índices compostos garantem performance nos relatórios regulatórios
- Seeds permitem ambiente demo realista

### Fase 7 pronta quando

- Associação-piloto opera 100% dentro do SCC
- Caso de referência documentado e mensurado
- Material institucional pronto para aproximação com entidade nacional

---

## 6. Conclusão

O SCC não é um produto separado. É a evolução do que a CannabIA já é — com extensões disciplinadas nas exatas camadas em que a regulação exige. O backlog acima é a sequência executável dessa evolução, respeitando os invariantes do Art. 17 como regras arquiteturais não-negociáveis.

A próxima sessão deve abrir pela Fase 0 (P0.1 — migration `022`).
