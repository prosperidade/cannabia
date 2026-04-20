# Progresso 17 — Auditoria completa e roadmap de melhorias

Data: 2026-04-17

## Contexto

Apos fechamento das 8 sprints do plano original (progresso15 + progresso16),
executamos auditoria completa em 4 frentes paralelas: backend, frontend,
banco de dados e operacao/observabilidade/deploy. Este documento consolida
os achados e define o roadmap a partir daqui.

Base de validacao ao iniciar a auditoria: `pytest -q` -> 90 passed, `tsc --noEmit` -> ok.

---

## Auditoria — achados por frente

### 1. Backend (src/ai, src/services, src/repositories, src/web/routes, src/integrations)

**ALTA:**
- Webhooks Twilio e Z-API stubs — `src/web/routes/realtime_notifications.py:136-153` retorna 200 OK sem processar nem validar assinatura; mensagens sao silenciosamente descartadas
- HMAC ausente no webhook Z-API (bearer token nao validado)
- `except Exception` muito amplos sem discriminacao em `ai/chains.py:214,332,431,478` e `ai/memory.py:83-169` (~50+ ocorrencias) — erros reais misturados com bugs
- Logica de negocio vazando para routes — `src/web/routes/org_management.py:40-114` com SQLs inline + calculo hardcoded (`costs = revenue * 0.35` na linha 427)
- SMS channel levanta `NotImplementedError` em `src/services/campaign_service.py:566-568` — campanhas SMS quebram em runtime

**MEDIA:**
- `src/integrations/email.py:32-52` retorna False silenciosamente quando credenciais faltam — caller nao verifica
- Validacao de campos obrigatorios ausente em POSTs — `src/web/routes/atendimentos.py:103-108` usa `.get("field", "")` sem schema
- Upserts faltando `ON CONFLICT` em conversation/appointment repositories — risco de duplicatas em retries
- `print()` em `src/ai/telemetry.py:12` — deveria ser `logger.debug`

**BAIXA:**
- ChromaDB sem fallback se collection vazia em `src/knowledge/vector_store.py:27-39`
- Google Files API client instanciado sem verificar presenca da chave em startup

### 2. Frontend (app/, components/, lib/)

**ALTA:**
- 4 rotas do portal do paciente apontam para paginas inexistentes:
  - `frontend/app/p/layout.tsx:14` → `/p/consultas` (nao existe)
  - `frontend/app/p/pagamento/page.tsx:103` → `/p/consulta` (singular, nao existe)
  - `frontend/app/p/layout.tsx:10-15` → `/p/documentos` (nao existe)
  - `frontend/app/p/dashboard/page.tsx:19,184` → `/p/consultas`

**MEDIA:**
- TODOs sem implementacao real de API:
  - `frontend/app/org/estoque/page.tsx:127,258` — addNewStock e addDispense nao chamam backend
  - `frontend/app/org/campanhas/page.tsx:257,266` — error handling vazio
  - `frontend/app/med/retornos/page.tsx:397` — botao sem navegacao
- MOCK_ACTIVITY placeholder em `frontend/app/admin/usuarios/page.tsx:144`
- Estado loading/apiError declarado mas nao renderizado em multiplas telas (atendimentos/[id], med/botanical, med/inteligencia, med/ensaios, org/relatorios)
- Inputs sem labels/aria-label em admin/knowledge, admin/tenants
- stockValue "R$ 84k" hardcoded em `frontend/app/org/estoque/page.tsx:393`

**BAIXA:**
- Dead code em `components/chat/` (ChatCanvas, ChatInput, ChatBubble, SliderPicker nunca importados)
- Dead code em `components/medical/` (BiometryCard, DifferentialDiagnosisCard, ScientificEvidenceCard, TreatmentSummaryCard nunca importados)
- `components/ui/error-boundary.tsx` nunca usado
- Componentes legados em `components/ui/` (duplicacao com `components/ui-tw/`)

### 3. Banco de dados (migrations 000-021)

**ALTA:**
- `patients.user_id` sem FK para `users.id` (adicionado em M014)
- `users.email` sem UNIQUE constraint (adicionado em M015)
- `triage_links.token_hash` sem UNIQUE (M018) — risco de duplicacao
- `ai_audit_logs.input_payload/output_payload` JSONB sem GIN index — dashboards com filtros degradam
- Timestamps inconsistentes: M001 e M003 usam TIMESTAMP (sem fuso); M010, M013, M021 usam TIMESTAMPTZ (correto) — cross-table com NOW() falha multi-zone
- CHECK constraints ausentes em `patients.status`, `treatment_plans.status`, `anamnesis_reports.status` — VARCHAR(50) sem validacao de dominio

**MEDIA:**
- Indices compostos faltando: `(clinic_id, status, created_at)` em patients, appointments, conversations, payment_requests
- `(clinic_id, patient_id, created_at)` em medical_record_entries nao existe
- FK cascade inconsistente: `triage_links.issued_by → users(id)` sem ON DELETE; `conversation_messages.conversation_id` sem FK declarada
- `campaign_templates.created_by` sem FK para users

**BAIXA:**
- Tabela `users` sem `email_verified_at`, `otp_secret`, `mfa_enabled` — sem suporte a 2FA
- `ai_audit_logs` sem retention policy declarada — crescimento ilimitado
- `audit_trail.details` JSONB sem GIN index (OK se queries nao filtram por JSONB)

### 4. Operacao, observabilidade e deploy

**ALTA:**
- **Backup strategy ausente** — zero documentacao de backup/restore/retencao
- Forward-only migrations sem mecanismo de rollback (runbook:95-104 confirma)
- `DEFAULT_CLINIC_ID` em config.py nao esta em .env.example — dev nao sabe configurar

**MEDIA:**
- Sem CI/GitHub Actions — `.github/workflows/` ausente; pytest nao roda automatico antes de deploy
- Rate limiting in-memory (`_RATE_BUCKET` em `auth.py:7`) — nao escala multi-worker
- `POST /chat/handshake` e `POST /api/v1/triage/submit` sem rate limit visivel
- `SECRET_KEY` fallback "dev-secret-key-fallback" e `VERIFY_TOKEN` fallback "verify-token-dev" em `config.py:25,45` — risco se configuracao incompleta em prod
- `request_id` / `tenant_id` nao propagados consistentemente para logs em services
- `TELEMETRY_*` vars em config.py:76-77 ausentes em .env.example

**BAIXA:**
- PII em `logger.info` direto — `anamnesis_flow.py:117` loga nome+telefone; `email.py:48` loga email. Redaction so protege logs estruturados
- CSRF nao rotacionado apos login (token inicial permanece)
- Redis em requirements.txt mas sem probe em health.py (talvez nao use em prod)
- Procfile obsoleto vs render.yaml — definir canonico
- Runbook sem secao de disaster recovery / rollback de deploy

---

## Roadmap de melhorias

### Prioridade 1 — Criticas (fazer ja)

**Banco e integridade:**
1. Migration 022 — UNIQUE em `users.email`, `triage_links.token_hash`; FK em `patients.user_id`; CHECK em status de patients/treatment_plans/anamnesis_reports; GIN em `ai_audit_logs.input_payload/output_payload`
2. Migration 023 — padronizar TIMESTAMP -> TIMESTAMPTZ em M001 e M003 (colunas created_at/updated_at das tabelas legadas)

**Operacao:**
3. `.github/workflows/ci.yml` rodando `pytest -q` + `tsc --noEmit` em todo PR
4. `docs/runbook_backup.md` — politica de retencao, teste periodico de restore, criar scripts `migrations/down/` para rollback das migrations mais recentes
5. Completar `.env.example` — `DEFAULT_CLINIC_ID`, `TELEMETRY_*`, `PAYMENT_WEBHOOK_SECRET_*`

**Frontend:**
6. Rotas quebradas do portal do paciente — criar `/p/consultas`, `/p/documentos` OU remover links do layout. Decidir escopo do portal (ver memoria: "patient app separate" — app paciente sera sistema separado)

### Prioridade 2 — Medias (ciclo seguinte)

**Backend:**
7. Implementar validacao HMAC e parser em webhooks Twilio e Z-API OU desativar explicitamente com 503
8. Validacao Pydantic em POST endpoints (atendimentos, prescriptions) — substituir `.get("field", "")` por schemas
9. Extrair SQLs inline de `org_management.py` para repository; substituir calculo hardcoded `revenue * 0.35` por metrica real
10. SMS channel — implementar ou filtrar na UI; remover `NotImplementedError`

**Frontend:**
11. Estoque — conectar `addNewStock`/`addDispense` ao backend real
12. Campanhas — implementar feedback de erro (toast)
13. Med retornos — ligar botao de paciente ao atendimento correspondente
14. Renderizar loading/erro nas 5 telas que declaram estado mas nao exibem

**Seguranca:**
15. Migrar rate limiting para Redis (ja esta em requirements.txt) — funcionar multi-worker
16. Adicionar rate limit em `POST /chat/handshake` e `POST /api/v1/triage/submit`
17. Rotacionar CSRF token apos login
18. Mascarar PII em `logger.info` direto (nao so logs estruturados)

**Performance:**
19. Indices compostos: `(clinic_id, status, created_at)` em patients, appointments, payment_requests; `(clinic_id, patient_id, created_at)` em medical_record_entries

### Prioridade 3 — Baixas (cleanup continuo)

**Dead code:**
20. Remover `components/chat/` exceto ConditionSelector
21. Remover 4 cards nao usados em `components/medical/`
22. Remover `components/ui/error-boundary.tsx`
23. Decidir: deletar legado `components/ui/` ou migrar ultimos usos para `ui-tw/`

**Acessibilidade (WCAG 2.1 AA):**
24. Labels em inputs de busca (admin/knowledge, admin/tenants)
25. `aria-label` em botoes de paginacao/close

**Observabilidade:**
26. Propagar `g.request_id`/`g.tenant_id` para services via logging context
27. Health probe do Redis
28. Retention policy em `ai_audit_logs` (cron de cleanup apos N dias)

**Qualidade:**
29. Classificar `except Exception` genericos (50+ em ai/chains.py e ai/memory.py) — erros esperados vs bugs
30. Substituir `print()` em `ai/telemetry.py:12` por `logger.debug`
31. Resolver Procfile vs render.yaml — manter canonico

---

## Metodologia

Auditoria conduzida em 4 agentes paralelos com thoroughness variavel:
- Backend: very thorough — 14 achados (5 ALTA, 5 MEDIA, 4 BAIXA)
- Frontend: very thorough — 20+ achados em 10 categorias
- Banco: very thorough — 13 achados em 21 migrations
- Operacao: medium — 14 achados em 14 categorias

Todos os agentes operaram em modo leitura — nenhuma modificacao feita durante a auditoria.

---

## Proximos passos

Sessao atual comeca pela **Prioridade 1**:
- [ ] Migration 022 — integridade (UNIQUE, FK, CHECK, GIN)
- [ ] Migration 023 — padronizacao TIMESTAMPTZ
- [ ] CI GitHub Actions (pytest + tsc)
- [ ] Documentacao de backup/DR + scripts de rollback
- [ ] .env.example completo
- [ ] Decisao sobre rotas do portal do paciente

Sessoes seguintes avancam Prioridade 2 e 3 conforme foco do usuario.

---

## Historico de sessoes

| Data | Sessao | Entregas |
|------|--------|----------|
| 2026-04-16 | Abertura | Auditoria inicial + plano de 9 sprints (progresso15) |
| 2026-04-16 | Sprints 1-4 | Triage links, cockpit medico, inbox, regulatory |
| 2026-04-17 | Sprints 5-8 | Admin sem mocks, multi-tenancy, financeiro, hardening (progresso16) |
| 2026-04-17 | Auditoria | 4 frentes paralelas — 60+ achados, roadmap priorizado (este doc) |
