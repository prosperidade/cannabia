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
-- Estrutura atual controlada por migrations 000-017
schema_migrations         -- controle de versão/checksum das migrations
clinics                   -- tenant atual (clínica)
users                     -- usuários
user_clinics              -- vínculo usuário-clínica
patients                  -- pacientes
appointments              -- agendamentos/consultas
incoming_messages         -- mensagens recebidas (WhatsApp)
message_status_updates    -- status de mensagens
whatsapp_sessions         -- sessão/estado conversacional
anamnesis_reports         -- relatório estruturado de anamnese
ai_audit_logs             -- auditoria de execução de IA
audit_trail               -- trilha transversal de auditoria
alerts                    -- alertas
medical_history           -- histórico médico
monitoring                -- monitoramento
treatment_plans           -- planos de tratamento
scientific_references     -- referências científicas
ai_prompt_versions        -- versionamento de prompts
tenant_types              -- tipos de tenant
tenants                   -- tenant formal da plataforma
tenant_branding           -- base de white-label
tenant_integrations       -- integrações por tenant
user_tenant_roles         -- vínculo usuário-tenant-perfil
patient_timeline_events   -- timeline longitudinal mínima
medical_records           -- prontuário longitudinal
medical_record_entries    -- entradas clínicas do prontuário
knowledge_base_versions   -- versionamento da base de conhecimento
knowledge_documents       -- documentos indexados
billing_plans             -- catálogo de planos
billing_subscriptions     -- assinaturas
billing_usage             -- consumo por tenant
billing_events            -- eventos de cobrança
campaign_templates        -- templates de campanha
campaign_executions       -- execuções de campanha
campaign_recipients       -- destinatários por execução
prescriptions             -- prescrições estruturadas
b2b_orders                -- pedidos B2B
scheduled_followups       -- follow-ups D+3/D+7/D+15
iot_telemetry             -- telemetria temporal
symptom_diary             -- diário de sintomas
stock_inventory           -- estoque clínico
stock_dispensations       -- dispensações ao paciente
billing                   -- faturamento clínico operacional
knowledge_catalog         -- catálogo unificado de conhecimento
knowledge_monitors        -- monitores de fontes
clinic_members            -- view operacional sobre user_clinics
```

---

## 3.1. Governança atual de migrations

- O runner canônico é `src/infra/run_migrations.py`
- A tabela de controle é `schema_migrations(version, filename, applied_at, checksum)`
- `migrations/000_migration_tracking.sql` garante a existência da trilha antes das migrations normais
- O runner rejeita prefixos de versão duplicados antes da aplicação
- Em bases legadas, o runner normaliza registros sem checksum e atualiza filename canônico quando o conteúdo confere
- `scripts/setup_local.py` foi validado em 2026-04-15 com a sequência real de migrations `000-017` e seeds demo

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
| `anamnesis_reports` | Relatório clínico persistido da anamnese *(já existe — preservar)* |
| `consultations` | Consultas clínicas formais *(adaptar appointments)* |
| `medical_records` | Prontuário longitudinal (entidade agregadora) |
| `medical_record_entries` | Entradas individuais do prontuário |
| `treatment_plans` | Planos terapêuticos *(já existe — preservar)* |
| `prescriptions` | Prescrição estruturada e protocolo terapêutico *(já existe — preservar/expandir)* |
| `b2b_orders` | Encaminhamento operacional de pedidos vinculados à prescrição *(já existe — adaptar)* |
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
| `scheduled_followups` | Follow-ups pós-consulta já agendados *(já existe — preservar)* |
| `symptom_diary` | Diário de sintomas do paciente *(já existe — preservar)* |
| `iot_telemetry` | Telemetria longitudinal vinda de dispositivos *(já existe — expandir)* |

---

### 5.5. Entidades financeiras

| Tabela | Descrição |
|--------|-----------|
| `billing` | Faturamento clínico operacional simples *(já existe — adaptar)* |
| `billing_plans` | Catálogo de planos da plataforma *(já existe — preservar)* |
| `billing_subscriptions` | Assinaturas por tenant *(já existe — preservar)* |
| `billing_usage` | Consumo medido para cobrança *(já existe — preservar)* |
| `billing_events` | Eventos financeiros rastreáveis *(já existe — preservar)* |
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
| `knowledge_documents` | Documentos indexados *(já existe — preservar)* |
| `knowledge_base_versions` | Versionamento de lotes de ingestão *(já existe — preservar)* |
| `knowledge_catalog` | Catálogo unificado de artigos, legislação e guidelines *(já existe — preservar/expandir)* |
| `knowledge_monitors` | Monitores de atualização por fonte *(já existe — preservar)* |
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

## 9. Extensão para o Sandbox Compliance Core (SCC)

A partir de 2026-04-19, este modelo passa a ser estendido pela série SCC para atender à RDC nº 1.014/2026 e ao Sandbox Regulatório da ANVISA. As extensões não reescrevem o modelo atual; elas se somam a ele, preservando compatibilidade com `clinic_id` e introduzindo gradualmente a discriminação por `tenant_type` (clínica, associação, médico autônomo).

### 9.1. Entidades novas do SCC

- `associations` — evolução tipada de `clinics` para tenants do tipo associação, com campos estatutários.
- `association_members` — vínculo formal pessoa-associação com status e vigência.
- `technical_responsibles` — Responsáveis Técnicos com habilitação validada.
- `sops`, `sop_versions`, `sop_trainings`, `sop_evidences`, `sop_deviations`, `capa_actions` — biblioteca de SOPs e ciclo de qualidade.
- `seed_lots`, `genetic_matrices`, `plants`, `cultivation_batches`, `harvests`, `extractions`, `api_vegetables`, `preparations`, `dispensations` — cadeia de rastreabilidade seed-to-patient.
- `traceability_events` — log append-only de todos os eventos de rastreabilidade, com hash encadeado (SHA-256 + `previous_hash`).
- `lab_analyses` — laudos analíticos com perfil de canabinoides, vinculados a eventos de rastreabilidade.
- `adverse_events`, `pharmacovigilance_notifications` — farmacovigilância estruturada.
- `sanitary_risks`, `risk_controls` — matriz de riscos sanitários.
- `sandbox_projects`, `sandbox_protocols`, `sandbox_indicators`, `sandbox_submissions` — gestão do Projeto Experimental.
- `blockchain_anchors` — registros de ancoragem em blockchain pública com prova associada.
- `regulatory_reports` — relatórios gerados e submetidos.

### 9.2. Extensões a entidades existentes

- `clinics` → evolução para `tenants` com discriminador de tipo.
- `patients` → vínculo opcional com `association_members` quando o tenant é associação.
- `prescriptions` → campos de conformidade regulatória específicos do sandbox.
- `audit_trail` → consolidação com hash encadeado cobrindo operação, qualidade, segurança, financeiro e IA.
- `ai_audit_logs` → extensão para auditar decisões de IA em triagem de farmacovigilância.

### 9.3. Princípios arquiteturais das extensões

- **Append-only** — tabelas de evento de rastreabilidade, farmacovigilância e auditoria sensível usam triggers que impedem `UPDATE`/`DELETE`.
- **Hash chaining** — cada evento carrega `event_hash`, `previous_hash`, `chain_id` e `chain_sequence` para formar Merkle chains internas.
- **Separação evento/contexto** — PII vive em tabelas mutáveis apagáveis sob LGPD; eventos imutáveis referenciam contexto por ID, nunca por valor.
- **Ancoragem externa** — raízes Merkle são periodicamente ancoradas em blockchain pública (Bitcoin via OpenTimestamps + Polygon) conforme `26_BLOCKCHAIN_ANCHORING_PROTOCOL.md`.

### 9.4. Série de migrations do SCC

As migrations físicas detalhadas (DDL, índices, triggers, seeds) ficam em `25_SCC_DATA_MODEL_AND_MIGRATIONS.md`. A numeração prevista começa em **024** e vai até **036**, preservando os slots **022** e **023** já reservados para os ajustes de integridade e padronização `TIMESTAMPTZ` do `docs/progresso17_auditoria_completa_e_melhorias.md`.

---

## 10. Conclusão

A CannabIA já possui base de dados real e aproveitável. O trabalho agora é conduzir uma **evolução disciplinada** do modelo existente para suportar a nova definição da plataforma, **incluindo o Sandbox Compliance Core** como camada de extensão coerente com a base atual.

A estratégia correta é preservar o que foi bem estruturado, adaptar o que precisa amadurecer e introduzir novos domínios onde o sistema atual ainda não cobre toda a necessidade do produto — inclusive quando essa necessidade vem da regulação sanitária.
