# 11 — Análise de Lacunas de Implementação

## 1. Propósito do documento

Este documento registra a **análise de lacunas** entre o estado atual implementado da CannabIA e o modelo de plataforma aprovado na documentação estratégica, funcional e arquitetural.

Serve como a ponte entre documentação conceitual e o roadmap técnico de evolução.

---

## 2. Premissa central

A análise compara:

```
Plataforma atual real  vs.  Plataforma consolidada desejada
```

Não é comparação entre "ideia" e "sistema inexistente". É leitura estruturada do que existe e do que ainda precisa ser construído.

---

## 3. Método de classificação

| Categoria | Descrição |
|-----------|-----------|
| **Implementado e aderente** | Já existe e atende razoavelmente bem ao modelo aprovado |
| **Implementado, precisa adaptação** | Existe, mas precisa evoluir em estrutura, escopo ou nomenclatura |
| **Parcialmente implementado** | Existe apenas de forma incompleta ou embrionária |
| **Ainda não implementado** | Não existe de forma real no sistema |
| **Exige revisão estrutural** | Existe algo relacionado, mas o modelo atual não sustenta a evolução |

---

## 4. Visão geral por domínio

| Domínio | Situação |
|---------|---------|
| Backend modular | ✅ Implementado e aderente |
| Multi-tenancy inicial | ⚠️ Implementado, precisa adaptação |
| White-label completo | 🔶 Parcialmente implementado |
| Jornada do paciente | 🔶 Parcialmente implementada |
| Jornada do médico | 🔶 Parcialmente implementada |
| Prontuário longitudinal unificado | 🔴 Exige revisão estrutural |
| Acompanhamento semanal | 🔶 Parcialmente implementado |
| Alertas com escalonamento | 🔶 Parcialmente implementado |
| Billing e monetização | ❌ Ainda não implementado |
| Pagamentos e QR Code | ❌ Ainda não implementado |
| Integração PubMed | ❌ Ainda não implementado |
| Banco vetorial e conhecimento | 🔶 Parcialmente implementado |
| Auditoria de IA | ✅ Implementado e aderente |
| Auditoria transversal | 🔶 Parcialmente implementado |
| Tenant contratante amplo | 🔴 Exige revisão estrutural |

---

## 5. Análise detalhada por domínio

### 5.1. Backend e estrutura do projeto

**Estado atual:** Backend em Python/Flask com organização modular, app factory, blueprints e componentes de IA.

**Classificação:** ✅ Implementado e aderente

**Direção:** Manter a base e evoluir modularmente.

---

### 5.2. Multi-tenancy

**Estado atual:** Multi-tenancy baseado em `clinic_id`, com contexto em request e validação de pertencimento.

**Classificação:** ⚠️ Implementado, precisa adaptação

**Gap:** Expandir de clínica para: clínica, associação, médico autônomo.

**Direção:** Generalizar tenancy progressivamente para `tenant_id`.

---

### 5.3. White-label

**Estado atual:** Direção conceitual clara, mas sem domínio completo de branding, subdomínio, canais e identidade por tenant.

**Classificação:** 🔶 Parcialmente implementado

**Gap:** Criar estrutura real para branding, subdomínio, WhatsApp, e-mail e chave de IA por tenant.

---

### 5.4. Jornada do paciente

**Estado atual:** Partes do fluxo clínico existem, mas sem jornada formalizada com estados, eventos e timeline unificada.

**Classificação:** 🔶 Parcialmente implementada

**Gap:** Formalizar estados, lead, acolhimento, triagem, pagamento, transições e timeline.

---

### 5.5. Jornada do médico

**Estado atual:** Consulta e pipeline de IA contemplados, mas sem modelagem explícita da jornada médica completa.

**Classificação:** 🔶 Parcialmente implementada

**Gap:** Formalizar: caso recebido, revisão pré-consulta, resposta a alertas, timeline do médico.

---

### 5.6. IA clínica e operacional

**Estado atual:** Pipeline de IA estruturado com validações, custos e auditoria.

**Classificação:** ✅ Implementado e aderente

**Gap:** Reposicionar a IA como camada transversal da plataforma, não apenas módulo isolado.

---

### 5.7. RAG e banco vetorial

**Estado atual:** Sinais de implementação com embeddings e ChromaDB.

**Classificação:** 🔶 Parcialmente implementado

**Gap:** Formalizar governança, fontes, ingestão, curadoria, versionamento e integração com PubMed.

---

### 5.8. Prontuário longitudinal

**Estado atual:** Informações clínicas distribuídas em múltiplas tabelas sem entidade agregadora.

**Classificação:** 🔴 Exige revisão estrutural

**Gap:** Criar lógica central de prontuário com timeline clínica consolidada.

---

### 5.9. Acompanhamento do paciente

**Estado atual:** Sinais de monitoramento e alertas, mas sem domínio completo com questionários, score e escalonamento.

**Classificação:** 🔶 Parcialmente implementado

**Gap:** Criar/expandir: templates, respostas, classificação de risco, timeline, regras de ausência.

---

### 5.10. Alertas e escalonamento

**Estado atual:** Base para alertas existe, mas sem motor formal de severidade e SLA.

**Classificação:** 🔶 Parcialmente implementado

**Gap:** Formalizar níveis verde/amarelo/laranja/vermelho, fila, prazos, escalonamento e histórico.

---

### 5.11. Comunicação

**Estado atual:** Base para mensagens recebidas e status (WhatsApp).

**Classificação:** ⚠️ Implementado, precisa adaptação

**Gap:** Expandir para domínio completo: conversas, templates, entregas, notificações, transbordo.

---

### 5.12. Pagamentos e QR Code

**Estado atual:** Jornada aprovada exige pagamento e QR Code, mas sem domínio robusto implementado.

**Classificação:** ❌ Ainda não implementado

**Gap:** Criar: requisição de pagamento, QR Code, status, conciliação, vínculo com consulta.

---

### 5.13. Billing e monetização

**Estado atual:** Sem domínio robusto de planos, assinatura e billing recorrente.

**Classificação:** ❌ Ainda não implementado

**Gap:** Criar: planos, subscriptions, limites, billing do tenant, histórico comercial, banners.

---

### 5.14. Integrações científicas

**Estado atual:** Arquitetura comporta isso, mas sem domínio formal consolidado.

**Classificação:** ❌ Ainda não implementado

**Gap:** Criar: conector PubMed, pipeline de ingestão, metadados, curadoria.

---

### 5.15. Segurança e compliance

**Estado atual:** Base de autenticação, tenancy, rate limiting e auditoria de IA.

**Classificação:** ⚠️ Implementado, precisa ampliação

**Gap:** Expandir para auditoria clínica/financeira, eventos de segurança, LGPD, política de segredos.

---

## 6. Maiores lacunas estruturais identificadas

Em ordem de impacto:

1. **Generalização de clínica para tenant contratante** — impacta toda a plataforma
2. **Formalização do white-label por tenant** — impacta identidade e canais
3. **Unificação do prontuário longitudinal** — impacta gestão clínica
4. **Domínio completo de acompanhamento e alertas** — impacta diferencial do produto
5. **Domínio financeiro com QR Code e pagamentos** — impacta jornada do paciente
6. **Domínio de billing e monetização** — impacta modelo comercial
7. **Governança robusta de conhecimento e PubMed** — impacta diferencial científico
8. **Auditoria transversal além da IA** — impacta compliance e regulatório
9. **Modelagem formal de jornadas como estados e eventos** — impacta operação

---

## 7. Ativos fortes da base atual

A CannabIA já possui ativos que reduzem muito o esforço de evolução:

| Ativo | Impacto |
|-------|---------|
| Backend modular estruturado | Alto |
| Multi-tenancy inicial funcional | Alto |
| Banco relacional existente | Alto |
| Pipeline de IA já montado | Alto |
| Auditoria de IA já presente | Médio |
| Documentação técnica inicial | Médio |
| Base de comunicação iniciada | Médio |

---

## 8. Estratégia de evolução resumida

| Ação | Domínios |
|------|---------|
| **Reaproveitar** | Backend, users, patients, appointments, ai_prompt_versions, ai_audit_logs, mensagens |
| **Adaptar** | user_clinics, alerts, monitoring, incoming_messages |
| **Criar** | Billing, pagamentos, white-label, prontuário unificado, PubMed, timeline, auditoria transversal |
| **Refatorar** | Domínio clínico agregado, modelo de tenancy amplo, estados da jornada |

---

## 9. Regras aprovadas neste documento

- A CannabIA já possui base real e relevante
- A plataforma deve evoluir por adaptação, não por reconstrução total
- Os maiores gaps estão em tenancy ampliado, billing, pagamentos, acompanhamento, white-label e governança de conhecimento
- IA e base backend são ativos fortes
- O roadmap deve partir de lacunas reais

---

## 10. Conclusão

A CannabIA já está além da fase de protótipo conceitual. Existe uma base concreta, refatorada e tecnicamente promissora.

O desafio agora é fechar de forma disciplinada as lacunas entre a base atual e a plataforma formalmente definida nos documentos anteriores.

Este documento estabelece essa leitura de gap e prepara a próxima etapa: o roadmap de adaptação e refatoração incremental.
