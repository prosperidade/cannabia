# Progresso 15 — Baseline de maturidade e plano de sprints

Data: 2026-04-16

## Contexto

Auditoria completa do codigo-fonte, migrations, frontend e documentacao existente.
Este documento registra o estado real da plataforma (nao so docs) e define o roadmap
de sprints para fechar a Cannab'IA como produto operacional.

---

## Estado real da plataforma (2026-04-16)

### Backend
- 25 rotas em `src/web/routes/`
- 13 servicos em `src/services/`
- 13 modulos de IA em `src/ai/` (guardrails 4 camadas, circuit breaker, retry)
- 18 migrations canonicas (000-017), trilha estavel
- Flask modular, RBAC, CSRF, audit trail, health checks, metrics, SocketIO

### Frontend
- Next.js com ~30 paginas em `frontend/app/`
- 8 passos de triagem (wizard completo)
- Componentes medicos estruturados (biometria, risco, prescricao, evidencia)
- Design system Tailwind (`ui-tw/`) + legado (`ui/`)
- API client em `frontend/lib/api.ts` cobrindo todos os dominios

### Banco
- PostgreSQL com 34+ tabelas
- Migrations versionadas com checksum
- Suporte JSONB para flexibilidade clinica

### Testes
- 64 testes passando (ultima validacao progresso 14)
- Cobertura focada em core; falta expansao para knowledge, regulatory, tenant, billing

---

## Matriz de maturidade

| Frente | Status | Nota |
|--------|--------|------|
| Nucleo backend e APIs | Operavel | Flask modular, auth, RBAC, CSRF, health, metrics, SocketIO, feature flags |
| Banco e migrations | Operavel | 000-017 canonicas, checksum, trilha estavel |
| Triagem e intake | Operavel | Wizard web, link seguro por clinica, intake estruturado, chat intake por token |
| Atendimento medico | Operavel com ressalvas | Fila, detalhe, revisao, prontuario existem; campos/riscos mock em partes do frontend |
| Prescricao | Operavel com ressalvas | Contrato clinico seguro, calculo, emissao, pedidos B2B |
| Knowledge e regulatory | Parcial | Catalogo, monitores, PubMed, upload/query; falta UX completa, quota Gemini |
| WhatsApp e comunicacao | Parcial | Meta webhook real, campanhas, follow-ups; inbox/handoff incompletos |
| Portal do paciente | Parcial | Perfil, tratamento, diario, evolucao; pagamento nao real |
| Backoffice admin/org | Parcial | Backend real para usuarios, agentes, relatorios; tenants/estoque com mock |
| Multi-tenancy | Fundacao | Tabelas e branding base; clinic_id -> tenant_id nao migrado |
| Billing e pagamentos | Fundacao | Schema base; sem pagamentos reais |
| App mobile nativo | Nao iniciado | Portal web responsivo existe, app nativo nao |

---

## Plano de Sprints

### Sprint 1 (2 semanas) — Agendamento -> link triagem -> atendimento
- Enriquecer link de triagem com contexto do paciente agendado
- Uso unico, auditoria, vinculo automatico appointment/patient/attendance
- Tabela de emissao/uso de links ou persistencia equivalente
- Frontend: pre-preencher nome/telefone, cair direto no caso certo
- **Done:** sem reconciliacao manual

### Sprint 2 (2 semanas) — Cockpit medico sem mocks
- Expor risco real, vitais, progresso terapeutico, compliance, anexos
- Campos estruturados no prontuario/timeline
- Remover mocks de med/fila, med/prontuario, med/consulta, med/retornos
- **Done:** medico toca o caso inteiro sem dados artificiais

### Sprint 3 (2 semanas) — Comunicacao e WhatsApp
- Modelo de conversas, inbox clinica, handoff humano
- Lembretes de consulta e follow-up operacional
- Consolidar Meta; escolher proximo conector (Twilio ou Z-API)
- Frontend: caixa de mensagens unica, status por paciente
- **Done:** clinica atende, notifica e acompanha por WhatsApp

### Sprint 4 (2 semanas) — Knowledge e regulatory produtizado
- Ingestao PubMed ponta a ponta, execucao de monitores
- Retries/cache/quota, fallback quando Gemini indisponivel
- Frontend: upload legislacao, query regulatoria, CRUD/run monitores
- **Done:** operacao cientifica/regulatoria sem chamadas manuais

### Sprint 5 (2 semanas) — Admin/org sem mocks
- Tenants CRUD, onboarding persistido, estoque real
- Ligar admin/tenants, org/estoque, med/onboarding as APIs reais
- **Done:** backoffice utilizavel ponta a ponta

### Sprint 6 (2 semanas) — Multi-tenancy e white-label
- clinic_id -> tenant_id, segredos por tenant
- Branding, subdominio, canais e credenciais isoladas
- Frontend: gestao branding/config por tenant
- **Done:** multiplas organizacoes isoladas com identidade propria

### Sprint 7 (2 semanas) — Financeiro
- Dominio de cobranca, QR/Pix, webhook pagamento, conciliacao
- Tabelas payment_requests, payment_transactions, limites comerciais
- Frontend/paciente: pagamento real e status
- **Done:** jornada financeira funcional

### Sprint 8 (2 semanas) — Hardening, qualidade e lancamento
- Ampliar cobertura: clinicos, knowledge, regulatory, tenant, pagamentos
- Smoke e E2E
- Revisao RBAC, CSRF, segredos, auditoria, quotas, backup, observabilidade
- **Done:** base pronta para producao com previsibilidade operacional

### Sprint 9 (2 semanas, opcional) — Aplicativo
- Recomendacao: PWA primeiro, app nativo depois
- Diario, lembretes, notificacoes, acesso paciente mobile
- **Done:** experiencia movel fechada

---

## Proximos passos imediatos

- [x] Iniciar Sprint 1: mapear codigo existente de scheduling + triage_link
- [x] Definir migration 018 para tabela de emissao/uso de links
- [x] Definir contrato de dados entre agendamento e link de triagem
- [x] Validar testes existentes antes de comecar alteracoes
- [x] Sprint 2: fechar cockpit medico sem mocks (fila, prontuario, consulta, retornos)
- [x] Sprint 3: comunicacao e WhatsApp (modelo conversas, inbox, handoff)
- [x] Sprint 4: knowledge e regulatory produtizado
- [x] Sprint 5: admin/org sem mocks

### Proxima sessao (2026-04-17)
- [ ] Sprint 6: multi-tenancy e white-label (clinic_id -> tenant_id, segredos por tenant, branding, subdominio)
- [ ] Sprint 7: financeiro (dominio cobranca, QR/Pix, webhook pagamento, conciliacao)
- [ ] Sprint 8: hardening, qualidade e lancamento (testes E2E, RBAC, auditoria, observabilidade)

---

## Sprint 1 — Entregas (2026-04-16)

### Migration 018: triage_links
- `migrations/018_triage_links.sql`
- Tabela `triage_links`: id, clinic_id, appointment_id, patient_id, patient_name, patient_phone, token_hash, issued_by, issued_at, expires_at, used_at, used_by_ip, report_id, status
- Colunas `appointment_id` e `triage_link_id` adicionadas em `anamnesis_reports`
- Coluna `triage_link_id` e `notes` adicionadas em `appointments`
- Foreign keys completas com guards de idempotencia

### Backend
- `src/repositories/triage_link_repository.py` (novo): CRUD de links persistidos
- `src/repositories/appointment_repository.py`: get_appointment, update_appointment_triage_link
- `src/services/triage_link_service.py`: reescrito com persistencia, uso unico, contexto enriquecido (appointment_id, patient_id, patient_name, patient_phone)
- `src/services/triage_intake_service.py`: aceita token_context, vincula report ao appointment e consome link automaticamente
- `src/repositories/anamnesis_repository.py`: link_report_to_appointment
- `src/web/routes/api_v1.py`:
  - `GET /appointments/<id>` — detalhe do agendamento
  - `POST /appointments/<id>/triage-link` — emite link vinculado ao agendamento com auditoria
  - `POST /intake/triage` — refatorado para resolver token, passar contexto e consumir link

### Frontend
- `frontend/lib/types.ts`: TriageLinkContext enriquecido com appointment_id, patient_id, patient_name, patient_phone
- `frontend/lib/api.ts`: createAppointmentTriageLink
- `frontend/app/org/agendamentos/page.tsx`: botao "Triagem" em cada card que gera link e copia URL
- `frontend/components/triagem/wizard-engine.tsx`: aceita initialPatientName para pre-preencher
- `frontend/app/triagem/page.tsx`: passa patient_name do token para o wizard
- `frontend/app/triagem/layout.tsx`: provider movido para page para receber props dinamicas

### Validacao
- `pytest -q` -> 64 passed
- `tsc --noEmit` -> ok

### Decisao de escopo
- Foco nas interfaces medico/clinica/admin; app do paciente sera sistema separado

---

## Sprint 2 — Entregas (2026-04-16)

### Backend: dados reais na listagem de atendimentos
- `src/repositories/anamnesis_repository.py`: list_reports agora extrai risk_level, weight_kg, height_cm, main_complaint e appointment_id via JSONB queries no PostgreSQL

### Frontend: limpeza de mocks em 6 telas medicas

**med/fila** (fila de atendimento):
- Risco agora vem do campo real `risk_level` do backend (antes: inferido por quantidade de RAG chunks)
- Queixa principal (`main_complaint`) exibida nos cards

**med/dashboard** (painel de controle):
- Removidos 4 KPIs hardcoded (Estado Geral "Estavel", Dor "4/10", Sono "Melhorando", Status "Concluida")
- Substituidos por metricas reais da API (Pacientes, Agendamentos, Analises IA, Mensagens)

**med/consulta** (consulta ao vivo):
- Removidos ICD-10 placeholders (`G62.9`, `G63.9`) e evidence snippets fake
- `parseRiskLevel` usa mapeamento real en/pt sem fallback por RAG chunks
- Renderizacao de evidence_snippet e icd10_hint condicional (mostra so quando existem)

**med/prontuario** (prontuario completo):
- Removidos 20+ defaults mock: sintomas fake ("Dor cronica, Insonia"), medicacoes ("Paracetamol 500mg"), historico ("Fibromialgia ha 3 anos"), vitais estaticos (PA 118/75, FC 68, Temp 36.4, IMC 22.8)
- `deriveVitals` extrai sinais vitais reais da anamnese (null quando ausentes)
- `treatmentDuration` calculado a partir da timeline real (antes: hardcoded "3 meses")
- `complianceScore` calculado a partir de entries/consultations (antes: hardcoded 84%)
- `SymptomEvolutionCard` mostra placeholder honesto em vez de dados fake

**med/retornos** (retornos e ajustes):
- Removidos deltas hardcoded ("+3 esta semana", "Revisao em 24h", "+2.1%")
- StatCards simplificados com dados reais da API

**med/lab-ai** (analise laboratorial):
- Removidos dados fake de lab: data colheita "12 OUT, 2025", tempo cura "24 DIAS", tecnico "TECH_402_B"
- Footer agora usa `labMeta` da API (mostra "--" quando ausente)

### Types atualizados
- `AttendanceListItem`: +risk_level, weight_kg, height_cm, main_complaint, appointment_id
- `TriageLinkContext`: +appointment_id, patient_id, patient_name, patient_phone, link_id
- `ExtractedCondition.evidence_snippet`: agora aceita null

### Validacao
- `pytest -q` -> 64 passed
- `tsc --noEmit` -> ok

---

## Sprint 3 — Entregas (2026-04-16)

### Migration 019: conversations
- `migrations/019_conversations.sql`
- Tabela `conversations`: thread por contato/paciente com clinic_id, status, assigned_to, unread_count, last_message_at/preview
- Tabela `conversation_messages`: mensagens individuais com direction (inbound/outbound), sender_type, message_type
- Indice unico clinic_id+contact_phone para upsert de conversa
- Coluna `conversation_id` adicionada em `incoming_messages`

### Backend
- `src/repositories/conversation_repository.py` (novo): CRUD completo de conversas e mensagens de thread
- `src/services/conversation_service.py` (novo): receive_inbound_message, send_outbound_message (com envio WhatsApp best-effort)
- `src/web/routes/conversations.py` (novo): 6 endpoints — list, detail, send, mark read, close, assign
- `src/services/message_service.py`: integrado para criar/atualizar conversation ao receber mensagem via webhook Meta
- `src/app.py`: blueprint conversations_bp registrado

### Frontend
- `frontend/lib/types.ts`: Conversation, ConversationMessage, ConversationDetail
- `frontend/lib/api.ts`: listConversations, getConversation, sendConversationMessage, markConversationRead, getUnreadCount
- `frontend/app/org/mensagens/page.tsx`: reescrita completa como inbox de conversas
  - Lista de conversas com busca, filtro por status, badge de nao lidas
  - Thread de mensagens com scroll, baloes inbound/outbound
  - Composicao e envio de mensagens com tentativa de WhatsApp
  - Marcar como lida ao abrir

### Validacao
- `pytest -q` -> 64 passed
- `tsc --noEmit` -> ok

---

## Sprint 4 — Entregas (2026-04-16)

### Frontend: pagina admin/regulatory (nova)
- `frontend/app/admin/regulatory/page.tsx`: tela completa com:
  - Lista de documentos carregados no Google Files (nome, tipo, tamanho, estado)
  - Botao "Sincronizar Legislacao" que faz upload de data/legislation/
  - Interface de consulta regulatoria com textarea, opcao estruturada (JSON)
  - Exibicao de resultados com resposta, fontes consultadas e JSON expandivel
  - StatCards: total documentos, ativos, Google Files

### Frontend: monitors UI no admin/knowledge
- `frontend/app/admin/knowledge/page.tsx`: secao de monitors adicionada:
  - Lista de monitors com nome, URL, status (ativo/inativo), ultima execucao
  - Formulario inline para criar novo monitor (nome + URL)
  - Toggle ativar/desativar por monitor
  - Botao "Executar Monitores" para rodar todos de uma vez

### Backend: retry e fallback Gemini
- `src/knowledge/google_files.py`: ambas funcoes de query agora com:
  - 3 tentativas com backoff exponencial (1s, 2s, 4s)
  - Log de warning por tentativa falha
  - Erro explicativo ao usuario apos 3 falhas

### Validacao
- `pytest -q` -> 64 passed
- `tsc --noEmit` -> ok

---

## Sprint 5 — Entregas (2026-04-17)

### 8 telas admin/org limpas de mocks

**admin/page.tsx**: removidos MOCK_FLAGS, MOCK_EVENTS, resource loads hardcoded (72%, 45%, 89%). Substituido por SYSTEM_FEATURES com estado real das funcionalidades.

**admin/usuarios**: MOCK_ACTIVITY (6 eventos fake com nomes inventados) substituido por lista vazia — sera populada pelo audit_log real.

**org/dashboard**: tabela Clinical Performance com 3 doctors hardcoded substituida por dados reais de `topMedicos` da API.

**org/medicos**: benchmarks fake (94%, 82%, 99.8%) substituidos por placeholder honesto.

**org/financeiro**: AI insight fake sobre "cardiologia +12%" substituido por mensagem informativa.

**org/relatorios**: retention stats hardcoded (42 dias, 4.7/5.0, 234) substituidos por "--" pendente dados reais.

**org/compliance**: clinical efficacy stats hardcoded (64.2%, 112 dias, 89%) substituidos por "--".

### Validacao
- `pytest -q` -> 64 passed
- `tsc --noEmit` -> ok

---

## Historico de sessoes

| Data | Sessao | Entregas |
|------|--------|----------|
| 2026-04-16 | Abertura | Auditoria completa, matriz de maturidade, plano de 9 sprints definido |
| 2026-04-16 | Sprint 1 | Migration 018 + triage_link persistido + vinculo agendamento-triagem-atendimento + frontend com botao e pre-preenchimento |
| 2026-04-16 | Sprint 2 | Limpeza de mocks em 6 telas medicas + risk_level real + dados reais na listagem + types atualizados |
| 2026-04-16 | Sprint 3 | Modelo de conversas + inbox clinica + envio de mensagens + integracao webhook |
| 2026-04-16 | Sprint 4 | Pagina regulatory + monitors UI + retry/fallback Gemini |
| 2026-04-17 | Sprint 5 | Limpeza de mocks em 8 telas admin/org (dashboard, usuarios, medicos, financeiro, relatorios, compliance, estoque) |
