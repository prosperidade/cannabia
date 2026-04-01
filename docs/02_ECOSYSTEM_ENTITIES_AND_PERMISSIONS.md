# 02 — Entidades do Ecossistema e Permissões

## 1. Propósito do documento

Este documento define a **estrutura do ecossistema da CannabIA**, descrevendo as entidades operacionais, os vínculos entre elas, o modelo de tenancy, os perfis de acesso e a política inicial de permissões.

Serve como referência para arquitetura multi-tenant, modelagem de banco de dados, controle de acesso, jornadas operacionais e governança de dados.

---

## 2. Estrutura geral do ecossistema

A CannabIA opera como uma **plataforma white-label multi-tenant**, controlada por uma **organização-mãe** e distribuída por meio de tenants contratantes.

```
Organização-mãe (CannabIA)
    └── Tenant: Clínica
    └── Tenant: Associação
    └── Tenant: Médico Autônomo
            └── Médicos vinculados
            └── Agentes operacionais
            └── Pacientes
```

---

## 3. Organização-mãe

Responsabilidades:

- Governança técnica e manutenção do produto
- Administração comercial e onboarding de tenants
- Faturamento e gestão de planos
- Gestão de banners, mídia e monetização adicional
- Governança de fluxos e templates globais
- Supervisão de integrações e monitoramento da operação

> A organização-mãe **não é um tenant** de atendimento final. Ela é a provedora da infraestrutura.

---

## 4. Modelo de tenant

### 4.1. Tipos de tenant

| Tipo | Descrição |
|------|-----------|
| **Clínica** | Entidade com operação própria de atendimento médico e múltiplos médicos vinculados |
| **Associação** | Entidade com atendimento, relacionamento, encaminhamento e múltiplos médicos |
| **Médico autônomo** | Profissional que opera diretamente seu atendimento, agenda e acompanhamento |

### 4.2. Tenant como unidade de isolamento

O tenant é a **principal unidade operacional e lógica de isolamento** da plataforma. Todo dado sensível — pacientes, prontuários, mensagens, documentos, alertas, pagamentos e configurações — está contextualizado por tenant.

### 4.3. Configurações white-label por tenant

| Elemento | Configurável |
|---------|-------------|
| Nome e logotipo | ✅ |
| Cores e identidade visual | ✅ |
| Subdomínio próprio | ✅ |
| E-mail operacional | ✅ |
| Número de WhatsApp | ✅ |
| Chave de API da IA | ✅ |
| Equipe, agenda e fluxos | ✅ (conforme plano) |

---

## 5. Entidades do ecossistema

### 5.1. Tenant
Entidade contratante da plataforma com tipo, marca, plano comercial, limites operacionais e configurações white-label.

### 5.2. Usuário
Pessoa com acesso autenticado ao sistema. Pode representar administrador, médico, agente ou operador da organização-mãe.

### 5.3. Médico
Profissional responsável pela decisão clínica. Pode operar:
- Como tenant próprio (médico autônomo)
- Vinculado a uma clínica
- Vinculado a uma associação
- Com vínculo múltiplo (sempre contextualizado por tenant ativo)

### 5.4. Agente de atendimento e acolhimento
Responsável por: contato inicial, acolhimento, triagem, captação de informações, coleta de documentos, apoio ao agendamento e encaminhamento. Pode ser automatizado com transbordo para humano.

### 5.5. Agente de acompanhamento
Responsável por: envio de questionários, monitoramento de respostas, registro de observações, sinalização de alertas e sustentação da jornada pós-consulta.

### 5.6. Paciente
Usuário final vinculado ao tenant de origem. Percorre a jornada de entrada, triagem, consulta, prontuário e acompanhamento.

---

## 6. Regras formais de vínculo entre entidades

| Relação | Cardinalidade |
|---------|---------------|
| Organização-mãe → Tenants | 1:N |
| Tenant → Usuários | 1:N (por papel) |
| Tenant → Médicos | 1:N |
| Médico → Tenants | N:N (vínculo múltiplo, contexto isolado) |
| Tenant → Agentes | 1:N |
| Tenant → Pacientes | 1:N |
| Médico → Pacientes | N:N (dentro do contexto do tenant) |

### Regra de propriedade dos dados

- O prontuário é mantido dentro do tenant de origem
- Médico com vínculo múltiplo acessa apenas o contexto do tenant ativo
- Compartilhamento entre tenants exige consentimento explícito, vínculo formal e auditoria

---

## 7. Modelo de isolamento e escopo

| Nível de escopo | Aplicação |
|----------------|-----------|
| **Organizacional** | Organização-mãe — visão global |
| **Tenant** | Clínica, associação ou médico — visão operacional local |
| **Clínico-operacional** | Responsabilidade sobre atendimento, paciente, prontuário e alerta |

**Regra central:** nenhuma operação sensível pode ocorrer fora do escopo de tenancy.

---

## 8. Perfis do sistema

### 8.1. Perfis da organização-mãe

**Super Admin da Organização**
- Criar e gerenciar tenants
- Administrar contratos, planos e billing
- Supervisionar operação global
- Gerenciar banners, mídia e templates
- Configurar regras e integrações centrais

**Admin Operacional da Organização**
- Onboarding e suporte a tenants
- Apoio à configuração e acompanhamento comercial
- Sem acesso irrestrito ao conteúdo clínico detalhado

---

### 8.2. Perfis do tenant

**Admin do Tenant**
- Configurar marca white-label (logo, cores, subdomínio)
- Configurar número de WhatsApp e e-mail do tenant
- Configurar chave de API da plataforma de IA
- Gerenciar equipe, agenda e médicos vinculados
- Acompanhar relatórios e faturamento local

**Médico**
- Acessar anamnese estruturada e prontuário
- Revisar relatório científico e exames
- Registrar consulta e definir conduta clínica
- Ajustar dose e solicitar exames
- Responder alertas e definir retorno

**Agente de atendimento e acolhimento**
- Acolher e triagem inicial do paciente
- Coletar dados e documentos
- Enviar QR Code de pagamento
- Apoiar agendamento e confirmar etapas
- Transbordar para humano quando necessário
- **Sem autonomia clínica**

**Agente de acompanhamento**
- Enviar questionários semanais
- Acompanhar respostas e registrar observações
- Identificar sinais e acionar alertas
- **Não altera conduta clínica nem prescreve**

**Paciente**
- Fornecer dados e responder questionários
- Enviar documentos e acompanhar consulta
- Receber notificações e acompanhar pagamentos
- Acessa apenas dados do próprio contexto

---

## 9. Política inicial de permissões

### 9.1. Modelo adotado

```
RBAC + Escopo por tenant + Restrição clínica por responsabilidade
```

- O **perfil** define o tipo de ação permitida
- O **tenant** define onde a ação pode ocorrer
- O **contexto clínico** define sobre quais pacientes a ação é válida

### 9.2. Princípios obrigatórios

| Princípio | Descrição |
|-----------|-----------|
| **Menor privilégio** | Todo perfil acessa apenas o mínimo necessário para sua função |
| **Contexto explícito** | Nenhum usuário atua fora do tenant ao qual está vinculado naquele momento |
| **Responsabilidade clínica** | Ações clínicas relevantes são restritas ao médico |
| **Auditabilidade** | Toda ação sensível deve ser rastreável |

---

## 10. Matriz resumida de acesso

| Capacidade | Org-mãe | Admin Tenant | Médico | Agente Atend. | Agente Acomp. | Paciente |
|-----------|:-------:|:------------:|:------:|:-------------:|:-------------:|:--------:|
| Gerenciar plataforma | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Gerenciar tenants | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Configurar tenant | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Configurar WhatsApp/e-mail/API | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Ver prontuário clínico | Restrito | Conf. política | ✅ | ❌ | ❌ | ❌ |
| Registrar consulta | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Definir conduta/prescrição | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Conduzir triagem/acolhimento | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Enviar QR Code e agendar | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Enviar questionários | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Acionar alertas | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Responder questionários | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Enviar documentos | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## 11. Política de transbordo operacional

O atendimento pode começar com agente automatizado, mas deve sempre prever transbordo para humano quando:

- O paciente solicitar atendimento humano expressamente
- Houver dúvida complexa ou sensibilidade emocional
- Ocorrer falha de pagamento ou inconsistência documental
- For detectado sinal de risco clínico
- O fluxo automatizado não conseguir progredir

O transbordo pode ocorrer para:
- Agente humano da operação
- Operação do tenant
- Médico (quando houver necessidade clínica)

---

## 12. Implicações para banco de dados

A modelagem deverá prever, no mínimo:

```
organization, tenants, tenant_types, tenant_branding,
tenant_integrations, users, roles, permissions,
user_tenant_roles, professionals, patients,
patient_tenant_links, patient_professional_links,
agents, consultations, attendances, medical_records,
alerts, audit_logs, tenant_plans
```

---

## 13. Definições aprovadas neste documento

- A CannabIA possui uma organização-mãe central
- Os tenants contratantes são clínica, associação e médico autônomo
- O tenant é a principal unidade de isolamento
- Médicos podem ter vínculo múltiplo entre tenants
- Pacientes pertencem inicialmente ao tenant de origem
- Haverá agente de atendimento e acolhimento com transbordo para humano
- Haverá agente de acompanhamento
- **Não haverá perfil de enfermeiro** na primeira fase
- O Admin do Tenant configura marca, WhatsApp, e-mail e chave de API da IA
- A política de acesso será RBAC com escopo por tenant e responsabilidade clínica

---

## 14. Conclusão

A CannabIA deve ser operada como uma plataforma multi-tenant white-label com clara separação entre organização-mãe, operação contratante, papéis operacionais, papéis clínicos e papéis administrativos.

Essa separação é o que permite escala, segurança, clareza jurídica, boa governança e evolução sustentável do produto.
