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
| IA | Pipeline funcional com auditoria |
| Vetorial | ChromaDB persistido em disco |
| WhatsApp | Webhook Meta e envio de mensagens |
| E-mail | Integração SMTP simples |
| Agenda | Agendamento simples |
| Billing | Não implementado |
| Pagamentos | Não implementado |
| PubMed | Não implementado |

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
| `src/infra/run_migrations.py` | Executor local de migrations | Implementado |

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
| `tenant_types` | tenancy ampla | base dos tipos de tenant |
| `tenants` | tenancy ampla | tenant formal da plataforma |
| `tenant_branding` | white-label base | configuração inicial de marca |
| `tenant_integrations` | integrações por tenant | fundação inicial |
| `user_tenant_roles` | acesso/tenancy | fundação da evolução de permissões |
| `patient_timeline_events` | jornada clínica | timeline longitudinal mínima |
| `medical_records` | prontuário | entidade agregadora inicial |
| `medical_record_entries` | prontuário | entradas clínicas e snapshots |

### 6.2. Leitura de maturidade do banco atual

| Categoria | Situação |
|-----------|----------|
| Estrutura clínica inicial | Existe |
| Contexto multi-clínica | Existe |
| Auditoria de IA | Existe |
| Comunicação WhatsApp | Existe |
| Prontuário longitudinal | Foundation mínima implementada |
| Billing | Não existe |
| Pagamentos | Não existe |
| Branding por tenant | Não existe |
| Integrações por tenant | Não existe |
| Timeline do paciente | Foundation mínima implementada |
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
| setup de migrations | runner local ainda é simples e deve evoluir com a próxima fase |
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
