# 09 — Integrações e Serviços Externos

## 1. Propósito do documento

Este documento define a **arquitetura de integrações externas e serviços de apoio** da plataforma CannabIA, considerando o sistema já existente, as integrações já iniciadas e as adaptações necessárias para sustentar o modelo white-label, multi-tenant e orientado a jornadas.

---

## 2. Papel das integrações na CannabIA

As integrações não são acessórios: são parte estrutural da operação do produto.

A CannabIA depende de integrações para viabilizar:

- Entrada e relacionamento com pacientes (WhatsApp)
- Envio de mensagens e notificações operacionais
- Confirmações e agendamento
- Pagamentos por QR Code
- Busca e ingestão de conhecimento científico
- Processamento de IA
- Armazenamento de documentos
- Branding white-label por tenant

---

## 3. Princípios arquiteturais das integrações

| Princípio | Descrição |
|-----------|-----------|
| **Governança por tenant** | Integrações configuráveis no contexto do tenant |
| **Isolamento de credenciais** | Credenciais de um tenant nunca expostas a outro |
| **Resiliência** | Falhas de integração geram erro controlado, não derrubam a plataforma |
| **Auditabilidade** | Toda chamada relevante a serviço externo é rastreável |
| **Adaptabilidade** | Troca de fornecedor sem reescrever o domínio de negócio |
| **Compatibilidade** | Evolução sobre o que já foi iniciado |

---

## 4. Macro-domínios de integração

| Domínio | Serviços |
|---------|---------|
| **Comunicação** | WhatsApp, e-mail, notificações transacionais |
| **Financeiro** | QR Code, PIX, gateway de pagamento, conciliação |
| **IA e processamento** | Provedores de LLM, embeddings |
| **Conhecimento científico** | PubMed, bases científicas, fontes regulatórias |
| **Armazenamento** | Storage de exames, anexos, documentos clínicos |
| **Agenda e calendário** | Agenda interna; integrações externas futuras |
| **Observabilidade** | Monitoramento, logs, alertas técnicos |

---

## 5. Estado atual percebido das integrações

Com base na leitura do repositório, a CannabIA já apresenta:

| Integração | Estado |
|-----------|--------|
| WhatsApp Business API | Base iniciada (webhook, mensagens, status) |
| OpenAI | Em uso |
| Google Gemini / Embeddings | Em uso |
| SMTP/Gmail | Previsto |
| Render (deploy) | Configurado |

Esse estado atual deve ser **preservado e reorganizado** dentro de uma arquitetura mais ampla.

---

## 6. Integração com WhatsApp

### 6.1. Papel do WhatsApp na plataforma

Canal prioritário da CannabIA, sustentando:

- Entrada e acolhimento do paciente
- Triagem e coleta de informações
- Envio de documentos e QR Code
- Confirmação de consulta e lembretes
- Acompanhamento semanal
- Escalonamento para humano

### 6.2. Estado atual

- Webhook configurado
- Armazenamento de mensagens recebidas
- Armazenamento de status de mensagens
- Configuração por variáveis de ambiente

### 6.3. Direção futura

Evolução para domínio de comunicação robusto:

- Múltiplos números por tenant (se necessário)
- Fila de mensagens e templates
- Histórico por conversa com rastreio de entrega
- Automação com fallback humano
- Comunicação atrelada à jornada do paciente

### 6.4. Configuração por tenant

Cada tenant configurará: número de WhatsApp, credenciais relacionadas, identidade da comunicação. A organização-mãe mantém governança sobre limites e segurança.

---

## 7. Integração com e-mail

### Papel
- Notificações operacionais e mensagens institucionais
- Confirmações, suporte ao tenant, comunicação complementar ao WhatsApp

### Direção futura
- Envio por tenant com identidade do remetente por tenant
- Templates de notificação rastreáveis
- Histórico de falhas e integração com eventos de jornada

---

## 8. Integração com provedores de IA

### Estado atual

| Provedor | Uso |
|---------|-----|
| OpenAI | LLM de geração |
| Google Gemini | LLM de geração |
| Google Embeddings | Vetorização de conteúdo |

### Direção futura

- Camada abstrata com suporte a múltiplos provedores
- Credenciais configuráveis por tenant
- Versionamento de prompts e logs por execução
- Rastreio de custo
- Fallback controlado entre provedores

### Credenciais por tenant

Como aprovado, a chave de API da IA é configurada pelo próprio tenant. A arquitetura deve suportar:

- Armazenamento seguro da credencial
- Uso contextual por tenant
- Validação de credencial
- Possibilidade futura de chave centralizada

---

## 9. Integração com PubMed e fontes científicas

### Papel estratégico

Sustenta a camada científica e o diferencial do relatório clínico-informacional.

**Capacidades necessárias:**

- Busca por tema clínico, sintomas, condição e canabinoides
- Recuperação de metadados científicos
- Pipeline de ingestão de abstracts para curadoria

### Modos de operação

| Modo | Uso |
|------|-----|
| **Busca em tempo real** | Consultas pontuais ou enriquecimento dinâmico |
| **Ingestão periódica** | Formação do banco vetorial com curadoria governada (preferencial) |

### Outras fontes previstas

- Bases regulatórias
- Diretrizes clínicas
- Repositórios científicos curados
- Materiais institucionais internos

---

## 10. Integração com banco vetorial e pipeline de conhecimento

**Capacidades necessárias:**

- Ingestão e chunking de conteúdo
- Geração de embedding
- Armazenamento e consulta semântica
- Atualização e invalidação de conteúdo
- Logs de uso do conhecimento

---

## 11. Integração com pagamentos e QR Code

### Requisitos mínimos

| Funcionalidade | Descrição |
|---------------|-----------|
| Geração de QR Code | Emissão por consulta/serviço |
| Status de pagamento | Pendente, confirmado, expirado, com falha |
| Reconciliação | Conciliação com evento da jornada |
| Auditabilidade | Rastreio financeiro completo |

### Direção futura

Domínio de pagamento independente com abstração suficiente para troca de gateway no futuro.

> A regra de negócio deve falar com um **módulo de pagamentos**, não diretamente com o fornecedor específico.

---

## 12. Integração com agenda e calendário

### Estado atual

O sistema já possui fluxo de agendamento próprio.

### Direção futura

Inicialmente, agenda nativa da plataforma. Futuras integrações com calendários externos quando a operação exigir.

---

## 13. Armazenamento de documentos

**Requisitos:**

- Armazenamento seguro com vínculo a paciente e tenant
- Metadados do arquivo e histórico de upload
- Controle de acesso e trilha de uso do documento

**Conteúdos previstos:**
- Exames laboratoriais e de imagem
- Documentos médicos e prescrições prévias
- Materiais de suporte ao prontuário

---

## 14. Notificações e lembretes

A lógica de notificação deve ser **desacoplada do canal**:

> A regra dispara uma notificação. A camada de comunicação decide se será WhatsApp, e-mail, push ou outro meio disponível.

**Precisam suportar:**

- Confirmações e lembretes de consulta (24h e 1h antes)
- Questionários de acompanhamento
- Alertas operacionais e de reengajamento
- Notificações para médico e agente

---

## 15. Modelo de arquitetura de integrações

A CannabIA deve adotar uma **camada de integração desacoplada por adaptadores**:

```
Regra de negócio
    → Interface de domínio
        → Adaptador de fornecedor
            → Serviço externo
```

**Exemplos de adaptadores:**

```
WhatsAppProvider    EmailProvider
PaymentProvider     KnowledgeSourceProvider
LLMProvider         EmbeddingProvider
StorageProvider     NotificationProvider
```

Isso reduz acoplamento e facilita troca de provedor.

---

## 16. Logs e auditoria de integrações

Toda integração relevante deve registrar:

```
tenant_id, servico_usado, operacao_executada,
payload_resumido, status, horario, erro_se_houver,
identificador_externo, vinculo_com_entidade_negocio
```

Especialmente para: mensagens, pagamentos, IA, conhecimento, documentos e notificações.

---

## 17. Estratégia de adaptação da base atual

| Ação | Escopo |
|------|--------|
| **Reaproveitar** | Base WhatsApp, base de mensagens, base de IA com OpenAI/Google, configurações de deploy |
| **Adaptar** | Fluxo de mensagens → domínio de comunicação robusto; auditoria → auditoria transversal; configuração por ambiente → configuração por tenant |
| **Criar** | Módulo de pagamento/QR Code; integração científica PubMed; storage documental formal; camada de adaptadores por serviço |

---

## 18. Regras aprovadas neste documento

- A CannabIA depende estruturalmente de integrações externas
- WhatsApp é canal prioritário da plataforma
- E-mail é canal complementar importante
- Provedores de IA são parte central do produto
- PubMed é fonte estratégica de conhecimento
- Pagamentos e QR Code exigem camada própria
- Credenciais devem ter governança por tenant
- Integrações devem ser auditáveis
- A arquitetura deve abstrair fornecedores por adaptadores
- A evolução reaproveitará o que já foi iniciado

---

## 19. Conclusão

A arquitetura de integrações da CannabIA deve refletir a realidade operacional do produto: uma plataforma que depende de comunicação, IA, conhecimento, pagamentos, documentos e notificações para funcionar de ponta a ponta.

O sistema já possui base concreta em algumas dessas áreas. A direção correta é expandir essa base com método, abstração, governança e visão multi-tenant.
