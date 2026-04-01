# 00 — Estado Atual, Reestruturação e Adaptação

## 1. Propósito do documento

Este documento registra o **estado atual da plataforma CannabIA**, considerando que o sistema já possui base implementada, já passou por uma **reestruturação e refatoração relevantes**, e agora entra em uma fase de **organização documental, consolidação arquitetural e adaptação funcional** para suportar o modelo de plataforma aprovado.

Seu objetivo é evitar que a documentação principal seja lida como se a CannabIA estivesse sendo concebida do zero. A realidade é diferente: já existe sistema, já existe backend, já existe banco, já existe pipeline de IA, já existe documentação técnica parcial, e já houve trabalho importante de reorganização do código.

Este documento funciona como a **ponte** entre:

- o que já existe no sistema
- o que já foi refatorado
- o que está sendo reorganizado agora
- o que precisará ser adaptado para a próxima fase da plataforma

---

## 2. Premissa central

A CannabIA **não está sendo criada do zero**.

A plataforma já possui:

- Base backend implementada em Python/Flask
- Banco de dados relacional funcional (PostgreSQL)
- Fluxo clínico inicial modelado
- Pipeline de IA funcional com auditoria
- Lógica inicial de multi-tenancy por `clinic_id`
- Documentação técnica parcial no repositório
- Estrutura modular já reorganizada
- Reestruturação e refatoração já realizadas em partes importantes da aplicação

O trabalho atual é, portanto, um trabalho de:

- Releitura do que já existe
- Organização do conhecimento sobre a plataforma
- Consolidação da visão de produto
- Adaptação da base atual ao modelo aprovado
- Expansão estruturada do sistema existente

---

## 3. O que já existe hoje na plataforma

### 3.1. Base backend

Backend implementado em **Python/Flask**, com organização por módulos e responsabilidades funcionais — app factory, autenticação, blueprints, rotas organizadas, contexto de request e fluxo básico da aplicação.

### 3.2. Multi-tenancy inicial

Lógica inicial de multi-tenancy baseada em `clinic_id`, com resolução de contexto por request e controle de pertencimento do usuário ao contexto autorizado.

### 3.3. Banco de dados funcional

Schema relacional inicial com entidades clínicas, operacionais, usuários, pacientes, agendamentos, alertas, monitoramento e auditoria de IA.

Tabelas identificadas no repositório:

```
clinics, users, user_clinics, patients, appointments,
incoming_messages, message_status_updates, ai_audit_logs,
alerts, medical_history, monitoring, treatment_plans,
scientific_references, ai_prompt_versions
```

### 3.4. Camada de IA

Pipeline de IA estruturado com:

- Validação de entrada
- Processamento em etapas
- Apoio clínico e geração de relatório
- Uso de modelos externos (OpenAI, Google Gemini)
- Cálculo de custo e auditoria da execução

### 3.5. Documentação técnica existente no repositório

- `README.md` — visão geral e estrutura
- `DATABASE_SCHEMA.md` — modelo de dados
- `AI_MODULE_DOCUMENTATION.md` — pipeline clínico e auditoria
- `AUTHORIZATION_AND_MULTI_TENANCY.md` — isolamento por clínica
- `DEPLOYMENT_AND_PRODUCTION_GUIDE.md` — produção e Render

### 3.6. Comunicação e integrações iniciais

Base para comunicação e integração com WhatsApp, e-mail (SMTP/Gmail), provedores de IA e ambiente de deploy gerenciado (Render).

---

## 4. O que já foi reestruturado e refatorado

A CannabIA já passou por uma **reestruturação técnica relevante**, o que deve ser preservado e valorizado na evolução futura:

- Reorganização do backend por componentes e domínios
- Melhoria da separação de responsabilidades
- Estruturação do pipeline de IA com fluxo, validação e auditoria
- Formalização inicial da lógica de tenancy por clínica
- Fortalecimento da documentação técnica interna

---

## 5. O que mudou com a nova definição da plataforma

A leitura mais recente do produto ampliou a compreensão do que a CannabIA de fato será.

**Antes**, o sistema era visto principalmente como:
- Sistema clínico com IA
- Apoio à consulta médica
- Plataforma para uma clínica

**Agora**, a definição consolidada mostra que a CannabIA será:
- Uma plataforma **white-label multi-tenant**
- Operada por **clínicas, associações e médicos**
- Com **jornada completa do paciente**
- Com **apoio científico estruturado (RAG + PubMed)**
- Com **acompanhamento longitudinal pós-consulta**
- Com **operação assistida por agentes**
- Com **monetização recorrente por planos**
- Com canais, branding e integrações configuráveis por tenant

Essa ampliação de visão **não invalida o que foi feito**. Ela exige **adaptação do que já existe**.

---

## 6. Estratégia recomendada de evolução

| Categoria | Definição |
|-----------|-----------|
| **Reaproveitar** | Estrutura atual já atende bem ao novo modelo |
| **Adaptar** | Base boa, mas precisa evoluir em escopo, nomenclatura ou vínculo de domínio |
| **Refatorar adicionalmente** | Base aproveitável, mas insuficiente para a próxima fase |
| **Criar módulo novo** | Funcionalidade aprovada ainda não existe |
| **Reestruturar profundamente** | Modelagem atual desalinhada de forma estrutural |

---

## 7. Regra de interpretação dos demais documentos

Todos os documentos da CannabIA devem ser lidos sob **quatro lentes**:

1. **Estado atual implementado** — o que já existe concretamente
2. **Estado atual reestruturado** — o que já foi melhorado/refatorado
3. **Adaptação necessária** — o que precisa mudar no sistema atual
4. **Direção futura** — como o componente deve funcionar na plataforma consolidada

---

## 8. Exemplos de adaptação necessária já identificados

| Componente | Situação atual | Adaptação necessária |
|-----------|----------------|----------------------|
| Multi-tenancy | Baseado em `clinic_id` | Generalizar para `tenant_id` com tipos: clínica, associação, médico |
| White-label | Não formalizado | Criar domínio de branding, subdomínio, canais e API por tenant |
| Jornada do paciente | Fluxo clínico parcial | Formalizar ponta a ponta com estados, eventos e timeline |
| Prontuário | Informações dispersas | Unificar em estrutura longitudinal com entidade agregadora |
| Acompanhamento | Monitoramento básico | Evoluir para domínio com questionários, score e escalonamento |
| Billing | Ausente | Criar domínio comercial com planos, assinaturas e limites |
| Conhecimento/RAG | Base embrionária | Formalizar governança, curadoria, PubMed e banco vetorial |

---

## 9. Conclusão

A CannabIA deve evoluir a partir da base real que já possui. O caminho correto não é recomeçar, mas:

- Organizar o que já foi construído
- Consolidar a visão de produto
- Adaptar a estrutura atual com método
- Preservar os ganhos da refatoração já feita
- Conduzir a evolução futura com clareza arquitetural, funcional e documental

Este documento é a **referência inicial de contexto** para toda a documentação principal da plataforma.
