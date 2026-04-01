# 08 — Modelo de Domínio e Banco de Dados

## 1. Propósito do documento

Este documento define o **modelo de domínio e a arquitetura de dados** da plataforma CannabIA, partindo da base já existente no sistema e estabelecendo as adaptações necessárias para suportar o modelo aprovado de produto, tenancy, white-label, jornadas, acompanhamento, IA, integrações e monetização.

---

## 2. Premissa de leitura

Este documento **não descreve um banco a ser criado do zero**.

A CannabIA já possui banco relacional implementado com entidades clínicas básicas. A função deste documento é reler o modelo atual, preservar o que já faz sentido e propor **adaptação progressiva** para o modelo futuro.

---

## 3. Estado atual do banco (identificado no repositório)

```sql
-- Tabelas já existentes
clinics                 -- tenant atual (clínica)
users                   -- usuários
user_clinics            -- vínculo usuário-clínica
patients                -- pacientes
appointments            -- agendamentos/consultas
incoming_messages       -- mensagens recebidas (WhatsApp)
message_status_updates  -- status de mensagens
ai_audit_logs           -- auditoria de execução de IA
alerts                  -- alertas
medical_history         -- histórico médico
monitoring              -- monitoramento
treatment_plans         -- planos de tratamento
scientific_references   -- referências científicas
ai_prompt_versions      -- versionamento de prompts
```

---

## 4. Estratégia de evolução do banco

| Abordagem | Quando usar |
|-----------|------------|
| **Preservar** | Tabelas e relações já aderentes ao novo modelo |
| **Adaptar** | Base boa, mas precisa evoluir em escopo ou nomenclatura |
| **Expandir** | Adicionar colunas ou relações para novos requisitos |
| **Criar** | Novos domínios ainda sem representação |
| **Refatorar** | Estrutura atual inviabiliza a evolução segura |

**Estratégia de migração de tenancy (clinic_id → tenant_id):**

```
Fase 1: Criar tabela tenants; vincular clinics a tenants
Fase 2: Introduzir tenant_id progressivamente nas novas entidades
Fase 3: Migrar lógica de acesso para tenant_id; manter clinic_id como subentidade
```

---

## 5. Domínios do modelo de dados

### 5.1. Entidades organizacionais

| Tabela | Descrição |
|--------|-----------|
| `organization` | Organização-mãe (CannabIA) |
| `tenants` | Unidades contratantes (clínica, associação, médico) |
| `tenant_types` | Tipos: clinic, association, doctor |
| `tenant_branding` | Configurações white-label por tenant |
| `tenant_integrations` | Credenciais e parâmetros por tenant |
| `tenant_plans` | Plano contratado e limites operacionais |

**Campos conceituais de `tenants`:**
```sql
id, organization_id, tenant_type, legal_name, display_name,
status, plan_id, created_at, updated_at
```

---

### 5.2. Entidades de acesso

| Tabela | Descrição |
|--------|-----------|
| `users` | Usuários autenticados *(já existe — preservar)* |
| `roles` | Perfis do sistema |
| `permissions` | Permissões por perfil |
| `user_tenant_roles` | Vínculo usuário-tenant-perfil *(evoluir de user_clinics)* |
| `user_sessions` | Sessões ativas |
| `audit_access_logs` | Trilha de acesso |

---

### 5.3. Entidades clínicas e operacionais

| Tabela | Descrição |
|--------|-----------|
| `patients` | Pacientes *(já existe — adaptar com tenant_id)* |
| `patient_profiles` | Dados detalhados do perfil |
| `professionals` | Médicos e especialistas |
| `patient_professional_links` | Vínculos paciente-médico |
| `leads` | Contatos pré-cadastro |
| `attendances` | Interações operacionais e acolhimento |
| `anamneses` | Coleta estruturada pré-consulta |
| `consultations` | Consultas clínicas formais *(adaptar appointments)* |
| `medical_records` | Prontuário longitudinal (entidade agregadora) |
| `medical_record_entries` | Entradas individuais do prontuário |
| `treatment_plans` | Planos terapêuticos *(já existe — preservar)* |
| `exams` | Exames solicitados |
| `attachments` | Documentos e arquivos vinculados |

---

### 5.4. Entidades de acompanhamento

| Tabela | Descrição |
|--------|-----------|
| `monitoring_programs` | Programas de acompanhamento |
| `questionnaire_templates` | Templates de questionários |
| `questionnaires` | Questionários enviados |
| `questionnaire_responses` | Respostas recebidas |
| `monitoring_events` | Eventos do acompanhamento |
| `alerts` | Alertas gerados *(já existe — expandir)* |
| `alert_escalations` | Histórico de escalonamento |
| `patient_timelines` | Timeline consolidada do paciente |

---

### 5.5. Entidades financeiras

| Tabela | Descrição |
|--------|-----------|
| `payment_requests` | Requisições de pagamento |
| `payment_transactions` | Transações processadas |
| `qr_code_payments` | QR Codes gerados e status |
| `billing_accounts` | Contas de billing por tenant |
| `subscriptions` | Assinaturas ativas |
| `invoices` | Faturas |
| `plan_limits` | Limites por plano |

---

### 5.6. Entidades de comunicação

| Tabela | Descrição |
|--------|-----------|
| `channels` | Canais configurados por tenant |
| `conversations` | Conversas ativas |
| `messages` | Mensagens *(evoluir de incoming_messages)* |
| `notifications` | Notificações disparadas |
| `notification_deliveries` | Status de entrega |
| `reminder_jobs` | Agendamento de lembretes |

---

### 5.7. Entidades de IA e conhecimento

| Tabela | Descrição |
|--------|-----------|
| `ai_runs` | Execuções de IA |
| `ai_run_inputs` | Entradas por execução |
| `ai_run_outputs` | Saídas por execução |
| `ai_prompt_versions` | Versionamento de prompts *(já existe — preservar)* |
| `rag_queries` | Consultas ao banco vetorial |
| `knowledge_sources` | Fontes de conhecimento |
| `knowledge_documents` | Documentos indexados |
| `knowledge_chunks` | Fragmentos para embedding |
| `knowledge_embeddings` | Vetores por chunk |
| `knowledge_usage_logs` | Rastreio de uso do conhecimento |

---

### 5.8. Entidades de auditoria

| Tabela | Descrição |
|--------|-----------|
| `audit_logs` | Log geral de ações |
| `clinical_audit_logs` | Ações clínicas sensíveis |
| `financial_audit_logs` | Ações financeiras |
| `integration_logs` | Chamadas a serviços externos |
| `security_events` | Eventos de segurança |

---

## 6. Prontuário longitudinal

O prontuário não deve ficar espalhado em múltiplas tabelas desconectadas. A solução é uma **entidade central `medical_records`** com itens em `medical_record_entries`.

**O que consolidar sob o prontuário:**

```
medical_history     → medical_record_entries (tipo: histórico)
treatment_plans     → medical_record_entries (tipo: plano)
monitoring          → patient_timelines + alert_escalations
alerts              → expandir com escalonamento e estados
```

---

## 7. Estratégia de adaptação por nível de impacto

| Impacto | Tabelas |
|---------|---------|
| **Baixo** (preservar) | `users`, `patients`, `appointments`, `ai_prompt_versions`, `ai_audit_logs` |
| **Médio** (adaptar) | `user_clinics` → `user_tenant_roles`, `alerts` → expandir, `monitoring` → acompanhamento, `incoming_messages` → comunicação |
| **Alto** (criar/refatorar) | Domínio de billing, white-label, prontuário unificado, conhecimento/RAG, timeline de jornada, auditoria transversal |

---

## 8. Regras aprovadas neste documento

- O banco atual será evoluído, não descartado
- O conceito de clínica será expandido para tenant contratante
- A adaptação será progressiva e compatível
- O modelo futuro suporta clínica, associação e médico autônomo
- O prontuário deve evoluir para estrutura longitudinal unificada
- Acompanhamento e alertas ganham domínio próprio
- Pagamentos e QR Code exigem modelagem dedicada
- IA e auditoria já existentes são preservadas e ampliadas
- White-label e billing exigem novos domínios de dados

---

## 9. Conclusão

A CannabIA já possui base de dados real e aproveitável. O trabalho agora é conduzir uma **evolução disciplinada** do modelo existente para suportar a nova definição da plataforma.

A estratégia correta é preservar o que foi bem estruturado, adaptar o que precisa amadurecer e introduzir novos domínios onde o sistema atual ainda não cobre toda a necessidade do produto.
