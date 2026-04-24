# Progresso 22 — Evidence Engine (F4.1/F4.2) + Fase 6 inteira

**Data:** 2026-04-23
**Escopo da sessão:** fechar as fases que faltavam do SCC com exceção do stack F3.3–F3.8 (pharmacovigilance services/routes) — totalizando o Evidence Engine (F4.1/F4.2), indexes/performance (F6.1), views/helpers (F6.2), seed data (F6.3) e o agregador compliance (F6.4).

---

## 1. Resumo executivo

6 commits entre `87c4931` e `f049bbb`:

- **F4.1** — `evidence_service.py` + `evidence_repository.py` (agregação longitudinal + correlação dose-efeito + classify_response_text PT-BR deterministico)
- **F4.2** — Provider `build_observational_study_data` + template `observational_studies/cohort_study_v1.md.j2` + categoria nova no registry (estudo observacional reproduzivel com `study_id` deterministico)
- **F6.1** — Migration `035_indexes_and_performance.sql` (11 indexes compostos + partials)
- **F6.2** — Migration `036_views_and_helpers.sql` (3 views + 2 funções: `fn_generate_event_hash`, `fn_verify_chain_integrity`)
- **F6.3** — Migration `037_seed_data_sandbox.sql` (função opt-in `seed_sandbox_defaults(tenant_id)` com 10 riscos + 10 SOPs)
- **F6.4** — `compliance.py` evoluído com `GET /compliance/overview` agregando 7 submódulos do SCC

Suite final: **1279 passed, 0 failed**. Delta vs início da sessão (1152): **+127 testes**.

Também: ajuste inicial no CI (`b73a881`) adicionando step `Enable PostGIS extension` antes das migrations no workflow (PostGIS já vinha da imagem postgis/postgis:16-3.5-alpine herdada de outra sessão).

---

## 2. Commits da sessão

| Hash | Descrição |
|------|-----------|
| b73a881 | ci: adiciona step "Enable PostGIS extension" antes das migrations |
| 87c4931 | svc(evidence): F4.1 — agregação longitudinal + correlação dose-efeito |
| 721eda3 | templates+svc: estudos observacionais via Evidence Engine — F4.2 |
| d6ae419 | migrations(035): indexes compostos e performance — F6.1 |
| 8500063 | migrations(036): views e funcoes helper — F6.2 |
| 4edc153 | migrations(037): seed data sandbox — F6.3 |
| f049bbb | routes(compliance): agregador dos 7 submodulos do SCC — F6.4 |

Todos pushados em origin/main.

---

## 3. Decisões arquiteturais desta sessão

### 3.1 Evidence Engine sem dependência de "F2.5 outcome capture"

progresso21 §5.2 registrou F4.1 como "bloqueado por F2.5 outcome capture" — uma dependência implícita que não estava no BACKLOG. Verificação prática mostrou que era **ilusória**: a telemetria pós-consulta (`scheduled_followups.response_text`/`responded_at`, `symptom_diary`, `iot_telemetry`) já existente basta para extrair desfechos longitudinais. F4.1 foi construído 100% sobre tabelas existentes, sem migration nova.

### 3.2 Classify_response_text deterministico, sem AI

Classificação de outcome de follow-up em `improved/unchanged/worsened` por keyword whitelist em PT-BR. Empate = `unchanged`. Consciente de que é heurística simples — documentado como limitação no estudo observacional. Vantagem: reproduzível, sem custo de AI, auditável. Evolução futura pode trocar por modelo NLP mantendo a interface `classify_response_text(text: str) -> str`.

### 3.3 EVIDENCE_ENGINE_VERSION como constante em regulatory_documents

Versão do algoritmo (atual: `"1.0"`) gravada em todo estudo observacional gerado. Bump quando `classify_response_text`, janelas default ou agregação pooled mudarem **semantica** — relatórios antigos permanecem auditáveis pelo label mesmo quando o código evolui.

### 3.4 study_id determinístico

Função pura de `tenant_id + condition_name + janelas + data_de_geracao`. Duas chamadas no mesmo dia com mesmos parâmetros geram mesmo `study_id`; mudança de qualquer parâmetro gera id diferente. Combinado com o `content_hash` SHA-256 do template_engine, permite submeter documento para F5 (anchoring) como prova de integridade.

### 3.5 Sample anonimizado em observational study

`sample_outcomes` no documento tem apenas `patient_id` numérico, sem `patient_name`. Alinha com LGPD para publicação externa. Teste `test_sample_outcomes_are_anonymized` trava esse contrato.

### 3.6 Renumeração de slot das migrations 035/036/037

BACKLOG_SCC previa as migrations F6.x em `034/035/036`. Na sessão de 2026-04-21 o slot 034 foi consumido por `034_review_workflows.sql` (F4.7). Daí a cascata:

- F6.1 → escrito como `035` (não 034)
- F6.2 → escrito como `036` (não 035)
- F6.3 → escrito como `037` (não 036)

Documentado no cabeçalho de cada migration afetada. BACKLOG_SCC atualizado para refletir.

### 3.7 Regular view em vez de materialized em `v_sandbox_indicator_dashboard`

Doc 25 §12.3 sugere materialized view para performance de dashboard. Escolhido regular view em v1 — dados sempre frescos, sem REFRESH manual ou cron. Indexes de F6.1 (`idx_siv_indicator_period_desc`) já sustentam a query. Converter para materialized quando volume justificar, em migration futura.

### 3.8 Seed de sandbox como função opt-in

`sanitary_risks` e `sops` têm `tenant_id NOT NULL`. Seed direto na migration acoplaria a um tenant específico ou iteraria sobre todos (comportamento impróprio em produção). Escolha: função `seed_sandbox_defaults(p_tenant_id)` opt-in via chamada explícita do operador. Idempotente via `ON CONFLICT DO NOTHING`. Helper `seed_sandbox_defaults_all_associations()` itera sobre tenants `association` sem catálogo ainda — útil em dev/homologação.

### 3.9 Compliance aggregator como fachada direta

HANDOFF_VALIDATION_REPORT §4.2 opção B previa `compliance.py` como dashboard que **consome** blueprints dedicados dos submódulos (governance/traceability/etc.). Como esses blueprints dedicados ainda não existem para todos os submódulos, `compliance.py` consome tabelas SCC diretamente em v1. Isolamento de falhas por submódulo: exceção em 1 não impede os outros de renderizar.

### 3.10 Checklist legado preservado em `/compliance`

Endpoint original `GET /compliance` (5 checks pré-SCC: CRM, patient status, audit_trail, stock, medical_records) mantido intacto por retrocompatibilidade com o frontend atual. Novo endpoint `/compliance/overview` é aditivo.

### 3.11 Score por submódulo = % de checks "ok"

Cálculo simples: `round(ok_count / total_checks * 100)`. Overall score = média simples dos 7 submódulos. Sem ponderação por severidade em v1 — evolução possível se o dashboard justificar (e.g., `pharmacovigilance` e `crypto` deveriam pesar mais que `quality`).

### 3.12 chain_id e chain_sequence como fonte de ordem em `fn_verify_chain_integrity`

Usa `LAG window function` sobre `ORDER BY chain_sequence` para derivar `expected_previous`. Primeiro evento (sequence=1) deve ter `previous_hash IS NULL`. Adulteração no meio da cadeia aparece como `valid=false` na linha correspondente com `expected_previous != actual_previous` para diagnóstico.

---

## 4. Stack consolidado do Evidence/Observational (F4.1 + F4.2)

```
build_observational_study_data(tenant, condition, **params)
  │
  ├─ _fetch_tenant(tenant)              ← tenants
  ├─ _fetch_primary_rt(tenant)           ← technical_responsibles
  │
  └─ build_evidence_summary              ← F4.1
       │
       ├─ aggregate_longitudinal_by_condition(cohort pooled)
       ├─ correlate_dose_effect(per-patient datapoints)
       ├─ summarize_followup_responses(D+3/D+7/D+15 por tipo)
       └─ list_responded_followups(sample anonimizado)
            │
            └─ (internamente) classify_response_text(response_text)
                              ← keyword-based PT-BR, determinístico

  ┓ shape para Jinja2 (StrictUndefined)
  ┃ limitations + reproducibility + EVIDENCE_ENGINE_VERSION
  ▼

template_engine.render("observational_studies/cohort_study", ctx)
  ├─ resolve() via registry.yaml
  ├─ Jinja2 render
  └─ content_hash SHA-256

→ RenderedDocument pronto para F5 (anchoring)
```

---

## 5. Estado do SCC

### 5.1 Fases fechadas até esta sessão

| Fase | Status | Notas |
|------|--------|-------|
| Fase 0 | ✅ 2026-04-19 | |
| F1.1 - F1.8 | ✅ 2026-04-20 | |
| F2.1 - F2.5 | ✅ 2026-04-20..21 | traceability_events + triggers append-only |
| F3.1, F3.2 | ✅ 2026-04-20 | Schemas pharmacovigilance + regulatory |
| **F4.1** | ✅ 2026-04-23 | Evidence Engine (31 testes) |
| **F4.2** | ✅ 2026-04-23 | Estudo observacional (12 testes) |
| F4.3, F4.4 | ✅ 2026-04-21 | Templates + engine |
| F4.5 | ✅ 2026-04-22 | 5 planos obrigatórios |
| F4.6, F4.7 | ✅ 2026-04-21 | Dossie + parecer + review workflows |
| F5.1 - F5.7 | ✅ 2026-04-20..21 | Anchoring stack completo |
| **F6.1** | ✅ 2026-04-23 | 11 indexes compostos (36 testes) |
| **F6.2** | ✅ 2026-04-23 | 3 views + 2 funções (19 testes) |
| **F6.3** | ✅ 2026-04-23 | Seed function opt-in (14 testes) |
| **F6.4** | ✅ 2026-04-23 | Compliance aggregator 7 submódulos (15 testes) |

### 5.2 Pendências SCC

**F3 stack (pharmacovigilance — camada de aplicação):**
- F3.3 — `adverse_event_service.py` — captura estruturada via WhatsApp/web/consulta
- F3.4 — extensão `ai/agents/regulatorio.py` com skill `triage_adverse_event`
- F3.5 — integração `integrations/vigimed.py` — notificação automática à ANVISA
- F3.6 — blueprint `pharmacovigilance.py` — captura, triagem, dashboard epidemiológico
- F3.7 — blueprint `regulatory_reporting.py` — dashboards ANVISA-ready com indicadores
- F3.8 — `tests/test_pharmacovigilance.py`

**F7 — piloto e parcerias** (trabalho humano de produto + jurídico, não dev puro):
- F7.1–F7.7 — carta de intenção, termo de participação, acordo de dados, comitê, implantação piloto, documentação de aprendizados, aproximação institucional

---

## 6. Pendências operacionais (ops/deploy — fora de dev puro)

Inalteradas desde progresso21, replicadas aqui para visibilidade:

- [ ] Deploy do contrato `SandboxAnchor` em Polygon Amoy (hardhat/foundry)
- [ ] Verificação do bytecode no Polygonscan
- [ ] Exportar `POLYGON_SANDBOX_ANCHOR_ADDRESS` em produção
- [ ] Instalar `web3` e `opentimestamps-client` no prod env
- [ ] Plugar `_ProductionPolygonClient.anchor()` com web3.py (sign + send tx + decode event)
- [ ] Plugar `_ProductionOtsClient.stamp()` com `opentimestamps-client`
- [ ] Criar `scripts/anchor_upgrade_cron.py` + agendar cron 5 min
- [ ] Multi-sig na wallet de deploy quando promover para mainnet
- [ ] Alertas + métricas conforme RUNBOOK §6

---

## 7. Pendências para a próxima sessão (amanhã)

Ordem sugerida de ataque:

### Prioridade 1 — F3 stack de pharmacovigilance

Já existem as migrations 031 (schema pharmacovigilance) e 032 (schema regulatory). Falta toda a camada de aplicação:

1. **F3.3** primeiro — `src/services/adverse_event_service.py` com:
   - `capture_adverse_event(tenant_id, member_id, description, severity, reported_via, ...)`
   - `list_events(tenant_id, filters)` para dashboards
   - Validações: severity whitelist ('mild','moderate','severe','life_threatening','fatal'), `reported_at >= event_onset_at`
   - Gancho para F3.4 e F3.5 (triagem IA + notificação VigiMed)

2. **F3.4** — skill `triage_adverse_event(report)` no `ai/agents/regulatorio.py`:
   - Input: payload completo do evento adverso
   - Output: severity sugerida + classificação + notify_required booleano
   - Grava em `adverse_events.ai_triage_result` JSONB

3. **F3.5** — `src/integrations/vigimed.py`:
   - Wrapper para VigiMed/Notivisa (lazy import de libs opcionais)
   - Dispatcher com `ANVISA_NOTIFICATION_PROVIDER=mock|vigimed|notivisa`
   - Mock client para CI; production clients opt-in

4. **F3.6** — blueprint `pharmacovigilance.py`:
   - POST `/adverse-events` — captura manual
   - GET `/adverse-events` — lista com filtros
   - POST `/adverse-events/<id>/notify` — dispara notificação
   - GET `/adverse-events/dashboard` — epidemiológico

5. **F3.7** — blueprint `regulatory_reporting.py`:
   - Dashboards ANVISA-ready sobre `v_sandbox_indicator_dashboard`
   - Agregações por período
   - Export em formato ANVISA (TBD na spec do edital)

6. **F3.8** — `tests/test_pharmacovigilance.py` cobrindo o pipeline completo

**Esforço estimado:** 2–3 sessões se fizer todos. Cada um é pequeno isoladamente; o gancho cruzado AE→IA→VigiMed é o que exige cuidado.

### Prioridade 2 — operações

Tickets operacionais listados na seção 6. Destravam testes e validação end-to-end com rede real (Polygon Amoy).

---

## 8. Referências técnicas para a próxima sessão

### 8.1 Tabelas e views relevantes para F3

- `adverse_events` — schema em migration 031, já populada por testes anteriores
- `pharmacovigilance_notifications` — schema em 031, target: 'vigimed'|'notivisa'|'internal_only'
- `sanitary_risks` / `risk_controls` — já tem seed via F6.3
- `v_sandbox_indicator_dashboard` — view de F6.2, usa latest_value + on_target
- Indexes compostos de F6.1 cobrem queries quentes:
  - `(tenant_id, reported_at DESC)` e `(tenant_id, severity, reported_at DESC)` em adverse_events
  - `idx_pv_notif_pending` partial sobre notificações sem response

### 8.2 Severity CHECK whitelist (migration 031)

```
severity IN ('mild', 'moderate', 'severe', 'life_threatening', 'fatal')
```

### 8.3 Convenção tenant_id/clinic_id

Mantida: `tenant_id == clinic_id` conforme docs/25 §11.3. Aplicada em todo código de F4.1+F6.4.

### 8.4 Padrão de testes adotado

- 1 módulo de teste por migration/serviço
- Fixture de tenant+clinic dedicada por teste (uuid suffix), cleanup transacional no yield pós
- Bypass de triggers append-only via `SET LOCAL session_replication_role = 'replica'` quando fixture precisa inserir dado adulterado (para validar detector)
- Classes `Test<Aspect>` agrupando por cenário

---

## 9. Como iniciar a próxima sessão

```bash
# 1. Subir stack local
docker start cannabia-postgis
python -m src.app &
cd frontend && npm run dev

# 2. Verificar suite
env\Scripts\python.exe -m pytest -q
# Esperado: 1279 passed

# 3. Ler este doc + progresso21 como base

# 4. Prioridade 1 da sessao anterior: F3.3 (adverse_event_service.py)
```

**Suite:** 1279 passed, 0 failed.
**Origin/main** sincronizado em `f049bbb`.
