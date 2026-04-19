# 16 — Inventário Técnico do Sistema Atual

## 1. Propósito do documento

Este documento registra o inventário técnico oficial da base atual da CannabIA, com foco em:

- módulos realmente existentes
- rotas implementadas
- tabelas existentes nas migrations
- integrações presentes no repositório
- aderência entre código atual e domínios aprovados na documentação principal

Ele funciona como a entrega operacional da Fase 1 de consolidação da base.

---

## 2. Escopo e método

Este inventário foi produzido a partir de leitura estática do repositório atual.

Fontes consideradas:

- `src/`
- `migrations/`
- `README.md`
- documentação consolidada em `docs/00` até `docs/15`

---

## 3. Snapshot atual do sistema

| Área | Situação observada |
|------|--------------------|
| Backend | Flask modular com blueprints e app factory |
| Auth | Flask-Login com usuário/senha |
| Tenancy | `clinic_id` ativo com foundation inicial de `tenant_id` |
| Banco | PostgreSQL com schema clínico-operacional inicial e foundation de tenant |
| IA | Fluxo especialista-first em `src/ai/clinical_flow.py` + pipeline legado para rollback |
| Vetorial | ChromaDB persistido em disco + catálogo unificado de conhecimento no PostgreSQL |
| WhatsApp | Webhook Meta e envio de mensagens |
| E-mail | Integração SMTP simples |
| Agenda | Agendamento simples |
| Billing | Foundation implementada, com maturidade operacional parcial |
| Pagamentos | Não implementado |
| PubMed | Busca e ingestão parcialmente implementadas via `AgenteExtrator` |

### 3.1. Atualização executiva — 2026-04-15

Pontos que precisam ser lidos como estado real mais recente da base:

- a camada de agentes já existe e está operacional no repositório
- o fluxo clínico principal deixou de depender do orquestrador como caminho crítico
- a base de conhecimento é híbrida:
  - ChromaDB para artigos científicos
  - Google Files API para legislação e documentos grandes
  - PostgreSQL para catálogo e monitores
- as rotas `/api/v1/knowledge`, `/api/v1/regulatory` e `/api/v1/admin/agents` já existem
- o MemPalace está configurado e em uso como memória fire-and-forget
- o setup local real (`scripts/setup_local.py`) foi validado com migrations `000-017` e seeds completos
- a trilha `schema_migrations` está normalizada com checksum canônico inclusive para `012`–`017`
- a pasta `data/legislation/` ainda não está populada com os documentos reais
- a suíte local está verde com `38` testes, mas ainda cobre pouco `knowledge` e `regulatory`

### 3.2. Atualização executiva — 2026-04-19

Pontos de atualização consolidando os ciclos de 2026-04-16 e 2026-04-17 (`progresso11`–`progresso17`) e a abertura da série SCC:

- `data/legislation/` passou a conter os documentos regulatórios canônicos (`RDC 327/2019`, `RDC 660/2022`, `Lei 11.343/2006`, `Resolução CFM 2.113/2014`), com upload real para Google Files API e 4 normas indexadas em `knowledge_catalog`
- contrato clínico mínimo para prescrição segura foi formalizado em `src/services/prescription_contract.py`, com `weight_kg`, `height_cm` e `prior_cannabis_use` como campos obrigatórios
- intake/triagem ganhou coleta antecipada desses campos no wizard web e endurecimento via link assinado por clínica em `src/services/triage_link_service.py`
- modelo de conversas e inbox clínica passou a existir em produção, com migration `019_conversations.sql`
- multi-tenancy evoluiu para operável com branding por tenant, integrações criptografadas (Fernet) e subdomínio via `src/tenancy.py`, suportado por `020_tenant_extensions.sql`
- domínio financeiro com emissão de Pix EMV (copia-e-cola com CRC16-CCITT), webhook conciliação validado por HMAC e auditoria em `payment_webhook_log`, suportado por `021_payment_requests_transactions.sql`
- suíte local verde com `90` testes (sprint 8), com cobertura estendida para pix payload, tenant secrets, tenancy subdomain e payment service
- sequência canônica de migrations hoje no repositório é `000`–`021`; os slots `022` e `023` ficam reservados para os ajustes de integridade (UNIQUE, FK, CHECK, GIN) e padronização `TIMESTAMPTZ` definidos no `docs/progresso17_auditoria_completa_e_melhorias.md`
- a série de documentos regulatórios `docs/23` a `docs/27` foi introduzida consolidando o **Sandbox Compliance Core (SCC)**, o programa piloto, a modelagem de dados do SCC, o protocolo de ancoragem em blockchain pública e a biblioteca de templates regulatórios
- rastreabilidade, farmacovigilância e proteção de dados pessoais passam a ser tratadas como **invariantes arquiteturais** (Art. 17 da RDC 1.014/2026), conforme `docs/10_SECURITY_COMPLIANCE_AND_AUDIT.md`, Seção 22

### 3.3. Atualização executiva — 2026-04-19 (sessão tardia)

Pontos entregues no fechamento da Fase 0 do `docs/BACKLOG_SCC.md`:

- `migrations/022_integrity_hardening.sql` escrita e pronta para aplicação: UNIQUE em `users.email` (case-insensitive, parcial), UNIQUE em `triage_links.token_hash` (substituindo o índice não-único de 018), FK `patients.user_id → users(id)` com `ON DELETE SET NULL`, CHECKs com whitelist em `patients.status`/`treatment_plans.status`/`anamnesis_reports.status`, GIN em `ai_audit_logs.input_payload` e `output_payload`
- `migrations/023_timestamp_standardization.sql` escrita e pronta para aplicação: conversão `TIMESTAMP → TIMESTAMPTZ` em 18 pares (tabela, coluna) das migrations 001 e 003, com loop declarativo e guards em `information_schema`
- `tests/test_migrations_integrity_hardening.py` com 30 testes estáticos validando estrutura, DDL específico, whitelists e idempotência (sem dependência de banco real)
- `docs/progresso18_integrity_hardening.md` registrando a sessão
- ambas as migrations **ainda não aplicadas** em ambiente local; a aplicação via `scripts/setup_local.py` fica como primeira missão da sessão seguinte no terminal

---

## 4. Inventário de módulos do backend

### 4.1. Núcleo da aplicação

| Arquivo | Papel | Situação |
|---------|-------|----------|
| `src/app.py` | App factory, login, blueprints, rotas base | Implementado |
| `src/config.py` | Configurações por ambiente | Implementado |
| `src/tenancy.py` | Contexto ativo por clínica com foundation de tenant | Implementado, em adaptação |

### 4.2. Infraestrutura

| Arquivo | Papel | Situação |
|---------|-------|----------|
| `src/infra/database.py` | Conexão e cursor de banco | Implementado |
| `src/infra/logging.py` | Configuração de logging | Implementado |
| `src/infra/security.py` | Redaction e controle simples de acesso | Implementado, precisa revisão |
| `src/infra/run_migrations.py` | Executor local de migrations | Implementado, versionado com checksum e normalização de legado |

### 4.3. Camada de IA

| Arquivo | Papel | Situação |
|---------|-------|----------|
| `src/ai/service.py` | Orquestração de caso clínico | Implementado |
| `src/ai/pipeline.py` | Pipeline clínico e relatório | Implementado |
| `src/ai/chains.py` | Chamadas aos provedores de IA | Implementado |
| `src/ai/validators.py` | Validação e anti prompt injection | Implementado |
| `src/ai/schemas.py` | Schemas de entrada e saída | Implementado |
| `src/ai/pricing.py` | Estimativa de custo | Implementado |
| `src/ai/prompts.py` | Prompts versionados em código | Implementado |
| `src/ai/telemetry.py` | Estrutura auxiliar | Presente |

### 4.4. Conhecimento e RAG

| Arquivo | Papel | Situação |
|---------|-------|----------|
| `src/knowledge/vector_store.py` | Persistência vetorial em ChromaDB | Implementado |
| `src/knowledge/embeddings.py` | Geração de embeddings Google | Implementado |

### 4.5. Integrações

| Arquivo | Papel | Situação |
|---------|-------|----------|
| `src/integrations/whatsapp.py` | Envio de mensagens WhatsApp | Implementado |
| `src/integrations/email.py` | Envio de e-mail SMTP | Implementado, simples |

### 4.6. Serviços de domínio atuais

| Arquivo | Papel | Situação |
|---------|-------|----------|
| `src/services/anamnesis_flow.py` | Fluxo conversacional de anamnese | Implementado |
| `src/services/message_service.py` | Processamento do webhook Meta | Implementado |
| `src/services/appointment_service.py` | Agendamento básico | Implementado |

### 4.7. Repositórios

| Arquivo | Papel | Situação |
|---------|-------|----------|
| `src/repositories/user_repository.py` | Usuários | Implementado |
| `src/repositories/tenancy_repository.py` | Contexto por clínica | Implementado, precisa adaptação |
| `src/repositories/patient_repository.py` | Pacientes | Implementado |
| `src/repositories/appointment_repository.py` | Agendamentos | Implementado |
| `src/repositories/message_repository.py` | Mensagens e status | Implementado |
| `src/repositories/anamnesis_repository.py` | Relatórios de anamnese | Implementado |
| `src/repositories/patient_timeline_repository.py` | Timeline longitudinal do paciente | Implementado |
| `src/repositories/medical_record_repository.py` | Foundation de prontuário longitudinal | Implementado |
| `src/repositories/ai_audit_repository.py` | Logs de IA | Implementado |
| `src/repositories/dashboard_repository.py` | Métricas do dashboard | Implementado |
| `src/repositories/session_repository.py` | Sessões WhatsApp | Implementado |
| `src/repositories/tenant_repository.py` | Acesso à nova camada de tenant | Implementado |

---

## 5. Inventário de rotas implementadas

### 5.1. Rotas base da aplicação

| Rota | Método | Finalidade |
|------|--------|------------|
| `/` | GET | Redireciona para dashboard |
| `/login` | GET, POST | Login |
| `/logout` | POST | Logout |
| `/whoami` | GET | Diagnóstico de autenticação |
| `/clinic-debug` | GET | Diagnóstico do contexto atual |
| `/ai/test` | POST | Execução do pipeline clínico |

### 5.2. Dashboard e operação

| Rota | Método | Finalidade |
|------|--------|------------|
| `/dashboard` | GET | Dashboard principal |
| `/historico/historico` | GET | Histórico de mensagens |
| `/admin/ai-metrics` | GET | Métricas de IA |
| `/scheduling/scheduling` | GET, POST | Agendamento |

### 5.3. Atendimentos

| Rota | Método | Finalidade |
|------|--------|------------|
| `/atendimentos` | GET | Lista de relatórios |
| `/atendimentos/<report_id>` | GET | Detalhe do relatório |
| `/atendimentos/<report_id>/revisar` | POST | Marcar relatório como revisado |
| `/atendimentos/<report_id>/prontuario` | POST | Salvar registro clínico no prontuário |

### 5.4. Realtime e webhooks

| Rota | Método | Finalidade |
|------|--------|------------|
| `/realtime/webhook/meta` | GET, POST | Webhook Meta |
| `/realtime/webhook/twilio` | POST | Skeleton |
| `/realtime/webhook/zapi` | POST | Skeleton |
| `/realtime/` | GET | Dashboard realtime |

---

## 6. Inventário de banco de dados atual

### 6.1. Tabelas existentes nas migrations

| Tabela | Domínio atual | Observação |
|--------|---------------|------------|
| `clinics` | tenancy atual | tenant atual ainda modelado como clínica |
| `patients` | clínico | usa `clinic_id` |
| `ai_prompt_versions` | IA | presente |
| `users` | acesso | papel global simples |
| `user_clinics` | acesso/tenancy | vínculo usuário-clínica |
| `appointments` | agenda | agendamento básico |
| `incoming_messages` | comunicação | mensagens WhatsApp |
| `message_status_updates` | comunicação | status de mensagens |
| `ai_audit_logs` | auditoria de IA | parte mais madura da trilha |
| `alerts` | alertas | modelo mínimo |
| `medical_history` | clínico | modelo simples |
| `monitoring` | acompanhamento | modelo mínimo |
| `scientific_references` | conhecimento | presente, pouco integrado |
| `treatment_plans` | clínico | modelo simples |
| `whatsapp_sessions` | conversacional | máquina de estados da anamnese |
| `anamnesis_reports` | atendimento/anamnese | persistência do relatório completo |
| `audit_trail` | auditoria transversal | trilha de ações sistêmicas |
| `tenant_types` | tenancy ampla | base dos tipos de tenant |
| `tenants` | tenancy ampla | tenant formal da plataforma |
| `tenant_branding` | white-label base | configuração inicial de marca |
| `tenant_integrations` | integrações por tenant | fundação inicial |
| `user_tenant_roles` | acesso/tenancy | fundação da evolução de permissões |
| `patient_timeline_events` | jornada clínica | timeline longitudinal mínima |
| `medical_records` | prontuário | entidade agregadora inicial |
| `medical_record_entries` | prontuário | entradas clínicas e snapshots |
| `knowledge_base_versions` | knowledge | controle de lotes/versionamento |
| `knowledge_documents` | knowledge | documentos indexados |
| `billing_plans` | billing | catálogo de planos |
| `billing_subscriptions` | billing | assinaturas por tenant |
| `billing_usage` | billing | medição de consumo |
| `billing_events` | billing | eventos financeiros |
| `campaign_templates` | campanhas | templates reutilizáveis |
| `campaign_executions` | campanhas | execuções disparadas |
| `campaign_recipients` | campanhas | destinatários por execução |
| `prescriptions` | clínico/prescrição | protocolo estruturado e limites de segurança |
| `b2b_orders` | comercial/operação | pedidos vinculados à prescrição |
| `scheduled_followups` | pós-consulta | follow-ups D+3/D+7/D+15 |
| `iot_telemetry` | monitoramento | série temporal por paciente |
| `symptom_diary` | acompanhamento | diário de sintomas |
| `stock_inventory` | operação clínica | estoque canábico |
| `stock_dispensations` | operação clínica | dispensação ao paciente |
| `billing` | operação clínica | faturamento simples |
| `knowledge_catalog` | knowledge/regulatório | catálogo unificado de artigos, normas e uploads |
| `knowledge_monitors` | knowledge/regulatório | monitores ativos por fonte |
| `clinic_members` | view operacional | alias de `user_clinics` para compatibilidade |

### 6.2. Leitura de maturidade do banco atual

| Categoria | Situação |
|-----------|----------|
| Estrutura clínica inicial | Existe |
| Contexto multi-clínica | Existe |
| Auditoria de IA | Existe |
| Comunicação WhatsApp | Existe |
| Prontuário longitudinal | Foundation mínima implementada |
| Billing | Existe como foundation + camada operacional simples |
| Pagamentos | Não existe |
| Branding por tenant | Foundation mínima implementada |
| Integrações por tenant | Foundation mínima implementada |
| Timeline do paciente | Foundation mínima implementada |
| Prescrição estruturada | Existe, ainda não embutida em todo fluxo principal |
| Knowledge catalog unificado | Existe |
| Monitores de conhecimento | Existe, com maturidade parcial |
| Questionários e respostas estruturadas | Não existe |

---

## 7. Inventário de integrações externas

| Integração | Estado atual | Observação |
|-----------|--------------|------------|
| Meta WhatsApp Business API | Implementada | webhook e envio de mensagens |
| SMTP/Gmail | Implementada | envio simples e global |
| OpenAI | Implementada | geração clínica |
| Google Gemini | Implementada | relatório científico |
| Google Embeddings | Implementada | embeddings para RAG |
| ChromaDB | Implementado | base vetorial local |
| Render | Configurado | deploy por `render.yaml` |
| Twilio | Não implementado | rota skeleton |
| Z-API | Não implementado | rota skeleton |
| PubMed | Não implementado | apenas previsto nos docs |

---

## 8. Fluxos realmente implementados hoje

### 8.1. Fluxo de anamnese via WhatsApp

Fluxo existente:

1. webhook Meta recebe mensagem
2. mensagem é persistida
3. detecção simples de termo crítico
4. fluxo conversacional coleta dados
5. pipeline de IA processa o caso
6. relatório é salvo em `anamnesis_reports`
7. médico recebe notificação por e-mail

### 8.2. Fluxo de agendamento

Fluxo existente:

1. usuário autenticado acessa o dashboard de agendamento
2. informa paciente e data
3. sistema cria paciente se necessário
4. sistema grava `appointments`

### 8.3. Fluxo de auditoria de IA

Fluxo existente:

1. requisição ou pipeline chama serviço de IA
2. entrada é validada
3. execução é registrada em `ai_audit_logs`
4. dashboard administrativo consome o resumo

---

## 9. Aderência por domínio aprovado

| Domínio aprovado | Situação atual | Classificação |
|------------------|----------------|---------------|
| Backend modular | Existe | Reaproveitar |
| Auth e sessão | Existe | Reaproveitar |
| Multi-tenancy amplo | Foundation criada, operação ainda por clínica | Adaptar |
| Fundação de tenant | Existe base inicial | Expandir |
| White-label | Não existe de forma real | Criar |
| Atendimento e acolhimento | Parcial via WhatsApp/anamnese | Adaptar |
| Jornada do paciente | Parcial | Adaptar |
| Jornada do médico | Parcial | Adaptar |
| Prontuário longitudinal | Foundation mínima implementada | Evoluir |
| Acompanhamento semanal | Muito parcial | Criar/Expandir |
| Alertas com severidade e SLA | Não existe formalmente | Criar/Expandir |
| Comunicação multi-canal | Parcial | Adaptar |
| RAG e conhecimento | Existe base embrionária | Expandir |
| Pagamentos | Não existe | Criar |
| Billing | Não existe | Criar |
| Auditoria transversal | Parcial | Expandir |
| Compliance e LGPD formal | Não existe | Criar |

---

## 10. Matriz operacional de decisão

### 10.1. Reaproveitar

| Componente | Evidência |
|------------|-----------|
| Estrutura Flask e blueprints | `src/app.py`, `src/web/routes/` |
| Pipeline de IA | `src/ai/` |
| Auditoria de IA | `src/repositories/ai_audit_repository.py` |
| Repositórios básicos | `src/repositories/` |
| Base vetorial | `src/knowledge/` |

### 10.2. Adaptar

| Componente | Evidência |
|------------|-----------|
| `clinic_id` para tenancy amplo | `src/tenancy.py`, `user_clinics`, `clinics` |
| Comunicação atual para domínio mais robusto | `incoming_messages`, `message_status_updates`, `src/services/message_service.py` |
| Agendamento simples para jornada formal | `appointments`, `src/services/appointment_service.py` |
| E-mail e WhatsApp globais para integrações por tenant | `src/config.py`, `src/integrations/` |

### 10.3. Expandir

| Componente | Evidência |
|------------|-----------|
| Alertas | tabela `alerts` |
| Monitoring | tabela `monitoring` |
| Conhecimento científico | `scientific_references`, ChromaDB |
| Segurança e autorização | `src/infra/security.py` |

### 10.4. Criar

| Componente | Necessidade |
|------------|-------------|
| `tenants`, branding e integrações por tenant | base do novo produto |
| timeline do paciente | suporte às jornadas |
| prontuário longitudinal | unificação clínica |
| questionários e respostas | acompanhamento |
| pagamentos e QR Code | jornada comercial |
| billing recorrente | monetização |
| integração PubMed | camada científica governada |

---

## 11. Dívidas e pontos de atenção remanescentes

| Item | Problema |
|------|----------|
| `user.role` vs `user_clinics.role` | semântica de papéis ambígua |
| setup de migrations | trilha canônica está saneada; resta manter disciplina de novas migrations e atualizar documentação operacional |
| integrações por tenant | WhatsApp, e-mail e IA ainda dependem de configuração global |
| migração ampla de domínio | `tenant_id` ainda não substitui `clinic_id` nas tabelas transacionais |

---

## 12. Próximas ações recomendadas

1. Fechar quick wins técnicos da sprint 1
2. Introduzir base de `tenant` em migration aditiva
3. Documentar transição `clinic_id -> tenant_id`
4. Preparar backlog da sprint 2 para jornadas, prontuário e acompanhamento

---

## 13. Conclusão

O sistema atual da CannabIA já possui base suficiente para sustentar evolução incremental. O inventário confirma que o caminho correto é:

- preservar a base modular existente
- adaptar tenancy e comunicação
- corrigir inconsistências imediatas
- introduzir novos domínios apenas onde o produto documentado já ultrapassou claramente a implementação atual
