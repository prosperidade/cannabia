# 07 — Arquitetura da Plataforma

## 1. Propósito do documento

Este documento define a **arquitetura sistêmica da plataforma CannabIA**, consolidando a visão estrutural do produto, seus módulos principais, as responsabilidades de cada camada, a lógica multi-tenant e os fundamentos técnicos necessários para sustentar a operação clínica, operacional, científica e comercial da solução.

---

## 2. Visão arquitetural

A CannabIA deve ser entendida como uma **plataforma operacional multi-tenant white-label**, com foco em atendimento assistido, consulta, apoio científico, prontuário e acompanhamento longitudinal.

A arquitetura precisa sustentar simultaneamente:

- Múltiplos tenants contratantes
- Múltiplos canais de entrada
- Usuários com perfis distintos
- Fluxos clínico e operacional integrados
- Camada de IA e RAG
- Prontuário longitudinal
- Automações de acompanhamento
- Pagamentos e validações operacionais
- Auditoria, segurança e governança

---

## 3. Princípios arquiteturais

| Princípio | Descrição |
|-----------|-----------|
| **Multi-tenancy como pilar central** | Todo componente sensível opera com isolamento explícito por tenant |
| **White-label governado** | Tenant personaliza dentro de arquitetura central governada |
| **Modularidade** | Módulos com responsabilidades claras, sem acoplamento excessivo |
| **IA como camada transversal** | IA atravessa múltiplos módulos com governança e rastreabilidade |
| **Auditoria por padrão** | Todo evento sensível deve ser rastreável |
| **Evolução progressiva** | Começar robusto e evoluir sem reescrever o produto inteiro |
| **Médico como autoridade clínica** | Camada clínica é assistida por IA, mas decidida por humano |

---

## 4. Camadas lógicas da plataforma

```
┌─────────────────────────────────────────────────┐
│         Camada de experiência e canais           │
│  Web · PWA · Android · iOS · WhatsApp · Email    │
├─────────────────────────────────────────────────┤
│      Camada de aplicação e orquestração          │
│  Jornadas · Regras · Auth · Permissões           │
├─────────────────────────────────────────────────┤
│             Camada de domínio                    │
│  Tenant · Paciente · Médico · Consulta           │
│  Prontuário · Alerta · Pagamento                 │
├─────────────────────────────────────────────────┤
│          Camada de IA e conhecimento             │
│  IA conversacional · RAG · Banco vetorial        │
│  Relatórios · Classificação                      │
├─────────────────────────────────────────────────┤
│              Camada de dados                     │
│  Banco relacional · Storage · Vetorial           │
│  Logs · Auditoria · Filas                        │
├─────────────────────────────────────────────────┤
│        Camada de integrações externas            │
│  WhatsApp · Email · Pagamentos · PubMed          │
│  Storage · Notificações                          │
└─────────────────────────────────────────────────┘
```

---

## 5. Macro-módulos da plataforma

### 5.1. Módulo de identidade, acesso e tenancy
Autenticação, sessão, perfis, RBAC, vínculos usuário-tenant, seleção de tenant, isolamento lógico, permissões por papel, contexto ativo.

### 5.2. Módulo de configuração white-label
Branding por tenant, subdomínio, logotipo, identidade visual, e-mail, WhatsApp, chave de API da IA, parâmetros operacionais.

### 5.3. Módulo de atendimento e acolhimento
Entrada do paciente, criação de lead, acolhimento, triagem, transbordo, coleta de informações e documentos, encaminhamento inicial.

### 5.4. Módulo de anamnese e preparação do caso
Anamnese assistida, consolidação de dados, ingestão de documentos, organização pré-consulta, estruturação do caso.

### 5.5. Módulo de agenda, consulta e prontuário
Agenda do médico, agendamento, lembretes, consulta, registro clínico, plano terapêutico, histórico longitudinal, exames.

### 5.6. Módulo de acompanhamento e alertas
Envio de questionários, coleta de respostas, classificação de sinais, alertas, escalonamento, timeline longitudinal do paciente.

### 5.7. Módulo de IA clínica e operacional
Apoio conversacional, organização da anamnese, relatórios assistidos, classificação inicial, suporte operacional orientado por IA.

### 5.8. Módulo de conhecimento, RAG e banco vetorial
Ingestão, indexação vetorial, recuperação semântica, integração com PubMed, curadoria, versionamento, governança de base global e por tenant.

### 5.9. Módulo financeiro e de validação
Geração de cobrança, QR Code, confirmação e conciliação de pagamento, bloqueios ou liberações por status financeiro.

### 5.10. Módulo de comunicação e notificações
Notificações transacionais, lembretes de consulta, mensagens de acompanhamento, confirmações, rastreio de comunicação.

### 5.11. Módulo de billing e monetização
Planos, limites por tenant, upgrades/downgrades, faturamento recorrente, serviços adicionais, mídia e banners.

### 5.12. Módulo de auditoria, compliance e observabilidade
Trilha de auditoria, logs sensíveis, histórico de ações, eventos clínicos/financeiros/de IA, monitoramento técnico.

---

## 6. Modelo arquitetural recomendado

**Monólito modular bem estruturado**, com possibilidade de evolução progressiva.

**Justificativa:**
- Velocidade de desenvolvimento
- Consistência de domínio
- Menor complexidade operacional inicial
- Boa governança de módulos
- Evolução gradual para filas, workers e serviços especializados quando necessário

> **Não** começar com microserviços puros. **Sim** a forte separação modular interna.

---

## 7. Domínios principais do sistema

```
identidade_e_acesso
tenancy_e_white_label
atendimento
anamnese
consulta_e_prontuario
acompanhamento
alertas
ia
conhecimento
billing
comunicacao
auditoria
```

---

## 8. Orquestração de fluxos

A CannabIA deverá possuir uma **camada de orquestração** responsável por:

- Coordenar jornadas e controlar estado de cada fluxo
- Disparar eventos e integrar módulos
- Reagir a mudanças de status
- Manter consistência de transições

Essa camada é essencial para: jornada do paciente, jornada do médico, acompanhamento, billing, alertas e notificações.

---

## 9. Processamento síncrono e assíncrono

| Síncrono | Assíncrono |
|---------|-----------|
| Login, cadastro | Envio de mensagens |
| Leitura de prontuário | Ingestão de documentos |
| Registro de consulta | Geração de relatório científico |
| Visualização de agenda | Busca em PubMed |
| | Classificação de acompanhamento |
| | Disparo de lembretes |
| | Ingestão de conteúdo vetorial |

---

## 10. Arquitetura de dados

| Componente | Uso |
|-----------|-----|
| **Banco relacional** | Entidades transacionais e estruturadas |
| **Armazenamento de documentos** | Exames, anexos, documentos clínicos |
| **Banco vetorial** | Memória semântica e recuperação contextual |
| **Logs e auditoria** | Rastreabilidade técnica e regulatória |
| **Fila/event store (futuro)** | Processamento assíncrono e integração orientada a eventos |

---

## 11. Evolução da arquitetura por fase

| Fase | Componentes |
|------|------------|
| **Inicial** | Monólito modular, banco relacional, storage, banco vetorial, integrações básicas |
| **Intermediária** | Workers, filas, processamento assíncrono robusto, observabilidade ampliada |
| **Avançada** | Serviços dedicados a IA, comunicação ou ingestão, maior segmentação de carga |

---

## 12. Componentes mínimos da plataforma

```
gateway_de_entrada          tenancy_manager
user_and_role_manager       patient_journey_manager
consultation_manager        medical_record_manager
monitoring_and_alerts_engine ai_orchestration_layer
rag_and_knowledge_engine    payment_integration_layer
notification_service        billing_service
audit_and_logging_layer     storage_layer
relational_database         vector_database
```

---

## 13. Regras aprovadas neste documento

- A plataforma será multi-tenant e white-label
- A arquitetura inicial é monólito modular
- A plataforma é organizada por módulos de domínio
- Há camada transversal de IA
- Há camada estruturada de RAG e conhecimento
- O tenant é unidade central de isolamento
- A plataforma suporta fluxos síncronos e assíncronos
- Eventos internos estruturam automações e integrações
- Auditoria é componente obrigatório
- A arquitetura evolui progressivamente sem ruptura

---

## 14. Conclusão

A CannabIA deve ser construída como uma plataforma modular, governada e progressivamente escalável, capaz de sustentar uma operação clínica e operacional complexa sem perder clareza estrutural.

Sua arquitetura precisa refletir a natureza real do produto: uma infraestrutura de atendimento, apoio científico, consulta, acompanhamento e relacionamento, operada em modelo white-label e sustentada por multi-tenancy, IA, eventos e auditoria.
