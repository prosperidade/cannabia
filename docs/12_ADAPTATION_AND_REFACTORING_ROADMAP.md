# 12 — Roadmap de Adaptação e Refatoração

## 1. Propósito do documento

Este documento define o **roadmap de adaptação e refatoração** da plataforma CannabIA, partindo do sistema existente, da reestruturação já realizada e das lacunas identificadas no documento anterior.

Transforma a leitura conceitual em um **plano de evolução prático, priorizado e executável**.

---

## 2. Premissa central do roadmap

A CannabIA **não será reconstruída do zero**.

A estratégia oficial é:
- Preservar o que já existe e está sólido
- Consolidar o que já foi refatorado
- Adaptar o que precisa amadurecer
- Criar novos módulos apenas onde houver lacuna real
- Reduzir risco de ruptura técnica e operacional

---

## 3. Objetivos do roadmap

| Objetivo | Descrição |
|---------|-----------|
| Reaproveitar a base atual | Aproveitar backend, banco, tenancy inicial e IA |
| Generalizar a plataforma | Evoluir de sistema centrado em clínica para multi-tenant amplo |
| Completar o modelo operacional | Fechar lacunas de jornada, acompanhamento, pagamento, billing e white-label |
| Consolidar governança | Fortalecer auditoria, segurança e compliance |
| Reduzir dívida futura | Fazer as adaptações certas agora |

---

## 4. Princípios de execução

- **Evolução incremental** — mudanças em fases com compatibilidade progressiva
- **Primeiro estruturar, depois expandir** — organizar domínios antes de adicionar funcionalidades
- **Evitar migração destrutiva precoce** — não quebrar o que hoje funciona
- **Preservar fluxo operacional** — mudanças arquiteturais respeitam a operação real
- **Documentação como instrumento de execução** — cada fase se apoia nos documentos consolidados

---

## 5. Estrutura geral do roadmap

```
Fase 1 → Consolidação da base e inventário
Fase 2 → Generalização da estrutura multi-tenant
Fase 3 → Jornadas e prontuário longitudinal
Fase 4 → Acompanhamento, alertas e comunicação
Fase 5 → White-label, pagamentos e monetização
Fase 6 → Governança, conhecimento, compliance e escala
```

---

## 6. Fase 1 — Consolidação da base e inventário

### Objetivo
Organizar a leitura do sistema atual, consolidar o que foi refatorado e preparar terreno para evolução segura.

### Ações principais
- Mapear módulos atuais vs. domínios aprovados
- Revisar banco atual com foco em reaproveitamento
- Identificar pontos de acoplamento indevido
- Classificar componentes em: reaproveitar / adaptar / expandir / criar

### Entregáveis
- Mapa do sistema atual
- Inventário de tabelas, rotas e fluxos existentes
- Classificação de impacto por domínio

**Prioridade: Imediata**

---

## 7. Fase 2 — Generalização da estrutura multi-tenant

### Objetivo
Evoluir do modelo atual centrado em `clinic_id` para um modelo de tenant contratante mais amplo, sem quebrar a base existente.

### Problema que resolve
O sistema atual suporta apenas o tipo "clínica". O produto aprovado exige: clínica, associação, médico autônomo.

### Ações principais
- Criar entidade `tenant` com tipologia
- Vincular estrutura atual de `clinics` ao conceito de tenant
- Adaptar progressivamente vínculos de usuários (`user_clinics` → `user_tenant_roles`)
- Introduzir camada de configuração por tenant (white-label base)

### Entregáveis
- Modelagem de tenant
- Vínculos usuário-tenant
- Base para white-label e billing por tenant
- Base para segregação mais robusta

**Impacto técnico: Estrutural, porém controlável**
**Prioridade: Muito alta**

---

## 8. Fase 3 — Jornadas e prontuário longitudinal

### Objetivo
Formalizar os fluxos do paciente e do médico no sistema e reorganizar a visão clínica em torno de um prontuário longitudinal claro.

### Problema que resolve
As partes do fluxo clínico existem, mas não como jornadas explícitas com estados, eventos e timeline unificada.

### Ações principais
- Modelar estados da jornada do paciente e do médico
- Estruturar eventos da jornada
- Criar timeline do paciente
- Consolidar entidade agregadora de prontuário (`medical_records`)
- Reorganizar partes dispersas do histórico clínico

### Entregáveis
- State machine da jornada
- Timeline clínica e operacional
- Estrutura de prontuário longitudinal
- Rastreabilidade completa do caso do paciente

**Impacto técnico: Alto**
**Prioridade: Muito alta**

---

## 9. Fase 4 — Acompanhamento, alertas e comunicação

### Objetivo
Transformar o acompanhamento em domínio real da plataforma, saindo de lógica parcial para operação longitudinal estruturada.

### Problema que resolve
A CannabIA quer ter acompanhamento contínuo como diferencial estratégico, mas isso exige mais do que monitoramento genérico.

### Ações principais
- Criar templates de questionários
- Criar motor de respostas de acompanhamento
- Implementar classificação de severidade (verde/amarelo/laranja/vermelho)
- Estruturar alertas com SLA e escalonamento
- Expandir domínio de mensagens e notificações
- Integrar acompanhamento à timeline do paciente

### Entregáveis
- Módulo de acompanhamento semanal
- Motor de alertas com escalonamento
- Histórico operacional de seguimento
- Integração com comunicação e notificação

**Impacto técnico: Alto**
**Prioridade: Muito alta**

---

## 10. Fase 5 — White-label, pagamentos e monetização

### Objetivo
Transformar a plataforma em um produto comercialmente operável conforme o modelo aprovado.

### Problema que resolve
A base funcional clínica precisa absorver de forma robusta o modelo white-label e a camada comercial/financeira.

### Ações principais
- Criar domínio de branding por tenant
- Configurar WhatsApp, e-mail e IA por tenant
- Implementar domínio de pagamento e QR Code
- Conectar pagamento com agendamento e liberação de jornada
- Criar domínio de billing (planos Basic / Pro / Premium)
- Estruturar base para banners e monetização complementar

### Entregáveis
- White-label real por tenant
- Configuração operacional por tenant
- Fluxo financeiro integrado à jornada
- Base de billing recorrente

**Impacto técnico: Alto**
**Prioridade: Alta**

---

## 11. Fase 6 — Governança, conhecimento, compliance e escala

### Objetivo
Consolidar a maturidade da plataforma em segurança, governança do conhecimento, auditoria transversal e preparação para crescimento.

### Ações principais
- Ampliar auditoria além da IA (clínica, financeira, segurança)
- Estruturar consentimento e LGPD
- Expandir base de conhecimento
- Integrar PubMed e pipeline de ingestão
- Estruturar curadoria e versionamento do conhecimento
- Melhorar observabilidade técnica
- Preparar arquitetura para filas e workers

### Entregáveis
- Auditoria transversal implementada
- Política de governança de conhecimento
- Integração científica governada
- Base de compliance mais robusta
- Preparação para escala

**Impacto técnico: Médio a alto**
**Prioridade: Alta (após domínios estruturais centrais)**

---

## 12. Prioridade executiva resumida

| Prioridade | Domínios |
|-----------|---------|
| **1 — Imediato** | Consolidação da base + Generalização de tenant |
| **2 — Muito alta** | Jornadas + Prontuário + Acompanhamento + Alertas |
| **3 — Alta** | White-label + Pagamentos + Billing |
| **4 — Alta (maturidade)** | Conhecimento + PubMed + Compliance + Escala |

---

## 13. Quick wins recomendados

Entregas de valor rápido sem reestruturação total imediata:

- Criar inventário técnico oficial do sistema atual
- Formalizar tenant como conceito no código e documentação
- Introduzir timeline da jornada sem refazer tudo de uma vez
- Melhorar estrutura dos alertas existentes
- Melhorar domínio de mensagens e notificações
- Criar placeholders de billing antes da automação completa
- Consolidar estados da jornada do paciente

---

## 14. Dependências entre fases

```
White-label       → depende de Generalização de tenant
Billing           → depende de Tenant + Planos
Pagamentos        → depende de Jornada do paciente
Acompanhamento    → depende de Prontuário + Timeline
PubMed            → depende de Camada IA/RAG
Compliance        → depende de Domínios + Auditorias
```

---

## 15. Blocos de execução sugeridos

| Bloco | Escopo |
|-------|--------|
| **A — Estrutura e domínio** | Tenant, usuários, permissões, configuração base |
| **B — Jornada e clínico** | Jornadas, anamnese, consulta, prontuário, timeline |
| **C — Seguimento e comunicação** | Questionários, alertas, mensagens, notificações |
| **D — Comercial e operação** | White-label, pagamentos, QR Code, billing |
| **E — Inteligência e governança** | RAG, PubMed, conhecimento, compliance, auditoria |

---

## 16. Critério de decisão: adaptar ou recriar

| Adaptar quando | Recriar quando |
|---------------|----------------|
| Base atual resolve parte importante do problema | Estrutura atual inviabiliza evolução segura |
| Acoplamento é controlável | Acoplamento é excessivo |
| Mudança pode ser incremental | Semântica atual do domínio está errada |
| Dívida técnica é aceitável | Adaptar sairia mais caro e frágil |

---

## 17. Indicadores de sucesso do roadmap

A evolução será bem-sucedida quando a CannabIA conseguir:

- ✅ Operar tenant de múltiplos tipos (clínica, associação, médico)
- ✅ Manter isolamento robusto por tenant
- ✅ Sustentar jornada ponta a ponta do paciente
- ✅ Sustentar jornada funcional do médico
- ✅ Manter prontuário longitudinal claro
- ✅ Operar acompanhamento semanal com alertas
- ✅ Usar white-label real por tenant
- ✅ Vincular pagamento ao fluxo operacional
- ✅ Oferecer billing coerente com o modelo comercial
- ✅ Manter uso de IA auditável e governado
- ✅ Integrar conhecimento científico com rastreabilidade

---

## 18. Regras aprovadas neste documento

- A evolução da CannabIA será incremental
- Não haverá reconstrução total como estratégia principal
- Tenancy é prioridade estrutural
- Jornadas e prontuário são prioridade clínica-operacional
- Acompanhamento e alertas são prioridade estratégica do produto
- White-label, pagamentos e billing são prioridade comercial
- Governança de conhecimento, auditoria e compliance são prioridade de maturidade
- A ordem de execução deve respeitar dependências entre domínios
- Quick wins são válidos, mas não substituem mudanças estruturais necessárias

---

## 19. Conclusão

A CannabIA já possui base concreta, refatoração relevante e ativos técnicos importantes. O desafio agora é conduzir a transição dessa base para uma plataforma mais ampla, organizada e comercialmente madura.

O caminho certo não é reconstruir tudo, mas adaptar com método. Este roadmap formaliza essa direção e transforma a documentação produzida em sequência prática de evolução.
