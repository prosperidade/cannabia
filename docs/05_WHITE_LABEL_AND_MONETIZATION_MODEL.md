# 05 — Modelo White-Label e Monetização

## 1. Propósito do documento

Este documento define o **modelo white-label** e a **estratégia inicial de monetização** da plataforma CannabIA, consolidando como a solução será entregue comercialmente e como essa entrega será transformada em receita recorrente e escalável.

---

## 2. O que significa white-label na CannabIA

No contexto da CannabIA, white-label significa que o tenant opera a plataforma com sua própria identidade institucional e seus próprios canais de relacionamento, enquanto a camada tecnológica, operacional e estrutural permanece sendo fornecida pela organização-mãe.

O tenant não percebe a CannabIA como "o sistema de outra empresa": percebe como **a própria plataforma digital da sua operação**.

---

## 3. Objetivo do modelo white-label

Permitir que clínicas, associações e médicos:

- Operem atendimento digital com sua própria marca
- Centralizem relacionamento com pacientes nos próprios canais
- Configurem integrações conforme sua operação
- Escalem sem precisar desenvolver tecnologia própria
- Utilizem IA e automações sem construir infraestrutura do zero

---

## 4. Elementos configuráveis por tenant

### Identidade institucional
- Nome da operação e logotipo
- Cores principais e identidade visual
- Textos institucionais básicos

### Presença digital
- Subdomínio próprio
- Páginas operacionais com experiência de marca

### Canais de comunicação
- Número de WhatsApp do tenant
- E-mail operacional do tenant

### Configurações de IA
- Chave de API da plataforma de IA usada pelo tenant
- Preferências operacionais de automação permitidas

### Configurações operacionais
- Equipe, médicos vinculados e agenda
- Regras de atendimento e acompanhamento (dentro do escopo do plano)
- Fluxos de mensagens e notificações

---

## 5. Limites do white-label

O tenant não controla:

- Arquitetura base do sistema
- Regras estruturais da plataforma
- Políticas globais de segurança
- Mecanismos centrais de auditoria
- Governança técnica da infraestrutura
- Módulos não contratados no plano

A customização do tenant existe **dentro de um modelo governado pela organização-mãe**.

---

## 6. Estrutura de planos comerciais

A monetização principal será feita por **assinatura mensal recorrente**, diferenciada por capacidade operacional e volume de pacientes.

### Plano Basic

**Público-alvo:** médico autônomo, operação pequena ou clínica em fase inicial.

| Item | Limite |
|------|--------|
| Pacientes ativos | Até 100 |
| Tenants | 1 |
| Usuários internos | Número reduzido |
| WhatsApp | 1 número |
| Funcionalidades | Atendimento, anamnese, consulta, acompanhamento básico, relatórios básicos, white-label essencial |

---

### Plano Pro

**Público-alvo:** clínicas estruturadas, associações em crescimento, médicos com volume maior.

| Item | Limite |
|------|--------|
| Pacientes ativos | 101 a 500 |
| Usuários internos | Múltiplos |
| Médicos | Múltiplos |
| Funcionalidades | Tudo do Basic + dashboards operacionais, alertas clínicos, white-label ampliado, prioridade intermediária no suporte |

---

### Plano Premium

**Público-alvo:** clínicas e associações maduras, alto volume, múltiplos fluxos.

| Item | Limite |
|------|--------|
| Pacientes ativos | Ilimitados |
| Usuários e médicos | Múltiplos |
| Funcionalidades | Tudo do Pro + subdomínio próprio, automações avançadas, dashboards gerenciais e clínicos, regras de escalonamento customizadas, onboarding dedicado, suporte prioritário, **SOPs & Quality Management (escopo reduzido)** e **Risk & Pharmacovigilance (escopo reduzido)** herdados do SCC |

---

### Plano Sandbox Ready

**Público-alvo:** associações de pacientes que pretendem concorrer ao Edital de Chamamento Público do Sandbox Regulatório da ANVISA (RDC nº 1.014/2026), ou que operam via autorização judicial e precisam migrar para o regime regulado até agosto de 2027.

Este plano é criado como **tier acima do Premium**, dedicado à entrega completa do Sandbox Compliance Core (SCC) definido em `23_SANDBOX_COMPLIANCE_CORE.md`.

| Item | Limite |
|------|--------|
| Pacientes ativos | Ilimitados |
| Usuários e médicos | Múltiplos |
| Funcionalidades | Tudo do Premium + **todos os sete submódulos do SCC em escopo completo**: Governance Hub, SOPs & Quality Management, Seed-to-Patient Traceability, Member-Patient Registry, Risk & Pharmacovigilance, Evidence & Real-World Data Engine, Regulatory Reporting & Audit Trail |
| Imutabilidade | **Ancoragem em blockchain pública ativa** (Bitcoin via OpenTimestamps + Polygon), conforme `26_BLOCKCHAIN_ANCHORING_PROTOCOL.md` |
| Templates regulatórios | Biblioteca completa dos cinco planos obrigatórios do Projeto Experimental + Dossiê de Elegibilidade + Parecer Final de Monitoramento, conforme `27_REGULATORY_TEMPLATES_LIBRARY.md` |
| Onboarding | Onboarding de compliance assistido por equipe dedicada da CannabIA |
| Suporte | Suporte prioritário com SLA diferenciado para submissão ao Edital |
| Dashboards | Dashboards regulatórios dedicados com indicadores ANVISA-ready |

**Precificação sugerida:** combinação de fee recorrente de plataforma + ticket por associado regularmente cadastrado + setup de compliance. O detalhamento de valores fica para documento comercial específico.

**Pontos não-negociáveis (invariantes do Art. 17 da RDC 1.014/2026):** rastreabilidade seed-to-patient, farmacovigilância e proteção de dados pessoais são tratadas como invariantes arquiteturais, não configuráveis por tenant. Ver detalhamento em `10_SECURITY_COMPLIANCE_AND_AUDIT.md` e `23_SANDBOX_COMPLIANCE_CORE.md`, Seção 4.4.

---

## 7. Critério principal de precificação

O critério principal de diferenciação dos planos será:

- **Volume de pacientes ativos**
- **Fluxo operacional**
- **Nível de estrutura contratada**

A precificação acompanha a maturidade do cliente e reduz barreira de entrada.

---

## 8. Política de custos de IA

Na fase inicial, a **chave de API da plataforma de IA é configurada pelo próprio tenant**.

**Implicações:**

- Reduz custo direto da CannabIA na fase inicial
- Simplifica a margem operacional
- Transfere consumo de IA para o contratante
- Permite flexibilidade na escolha do provedor

A CannabIA monetiza a **estrutura, automação, fluxo e plataforma** — não o token consumido, ao menos na fase inicial.

---

## 9. Receitas complementares

### 9.1. Banners e mídia da indústria
Espaços reservados para banners da indústria farmacêutica ou parceiros do ecossistema.

### 9.2. Serviços de implantação
- Setup inicial e ativação assistida
- Configuração de tenant e treinamento
- Implantação white-label

### 9.3. Serviços de customização
- Ajustes sob demanda
- Fluxos especiais e parametrizações adicionais

### 9.4. Futuras comissões de vendas
Intenção aprovada de explorar comissões no ecossistema (a ser formalizado juridicamente).

### 9.5. SKU de consultoria regulatória parceira

Vinculado ao plano Sandbox Ready, a consultoria jurídica é oferecida como **SKU separável**, em duas modalidades de contratação:

- **CannabIA Sandbox Ready (Plataforma)** — apenas a plataforma, sem camada jurídica.
- **CannabIA Sandbox Ready + Legal Desk** — plataforma + acesso a rede credenciada de escritórios parceiros especializados em cannabis medicinal e regulação sanitária.

A associação escolhe a modalidade no momento da contratação e pode migrar entre elas a qualquer tempo. A CannabIA pode trabalhar com mais de um escritório parceiro, oferecendo escolha à associação. O modelo jurídico e comercial da rede de escritórios fica detalhado em documento específico a ser produzido como extensão de `23_SANDBOX_COMPLIANCE_CORE.md`.

---

## 10. O que o tenant está comprando de fato

O tenant não compra apenas software. Ele compra:

- Estrutura de entrada e acolhimento de pacientes
- Triagem assistida e anamnese apoiada por IA
- Agendamento, pagamento e consulta integrados
- Prontuário longitudinal
- Acompanhamento semanal com alertas
- Centralização operacional
- Operação digital white-label
- Escalabilidade sem necessidade de tecnologia própria

---

## 11. Possíveis componentes de billing futuro

A documentação registra a possibilidade de evolução para:

- Cobrança por volume extra de pacientes
- Cobrança por usuário adicional
- Cobrança por integrações especiais
- Cobrança por automações customizadas
- Eventual cobrança por uso de IA (se a CannabIA internalizar esse custo)

Esses componentes são registrados como roadmap comercial, não como regra aprovada.

---

## 12. Estrutura conceitual de billing por tenant

A modelagem deverá suportar:

```
tenant_id, tenant_type, plano_atual, status_contrato,
limite_operacional, consumo_atual, status_financeiro,
historico_upgrades, servicos_adicionais_contratados,
espacos_midia_habilitados
```

---

## 13. Relação entre white-label e arquitetura

As decisões deste documento impactam diretamente a arquitetura da plataforma. O sistema deverá prever:

- Configurações por tenant
- Branding por tenant
- Subdomínio e canais por tenant
- Chaves de integração por tenant
- Módulos habilitados por plano
- Billing e limites por tenant
- Auditoria de configurações

---

## 14. Regras aprovadas neste documento

- A CannabIA será vendida em modelo white-label
- Os tenants contratantes serão clínica, associação e médico autônomo
- A organização-mãe permanece como provedora da infraestrutura
- Cada tenant poderá configurar marca, WhatsApp, e-mail e chave de API da IA
- A monetização principal será mensal e recorrente
- Os planos iniciais serão Basic, Pro e Premium
- A diferenciação comercial será baseada em volume e fluxo operacional
- A chave de IA será inicialmente responsabilidade do tenant
- Haverá monetização complementar por banners e mídia

---

## 15. Pontos ainda em evolução

- Valores concretos de cada plano
- Limites exatos de usuários por faixa
- Definição objetiva de "paciente ativo"
- Política de cobrança proporcional, cancelamento e inadimplência
- Regras formais de banners e mídia
- Política de comissionamento
- Política de suporte por nível de plano

---

## 16. Conclusão

A CannabIA deve ser posicionada comercialmente como uma **plataforma white-label de operação clínica e assistencial** — não apenas como software de prontuário ou ferramenta de IA.

Seu modelo de monetização precisa refletir essa amplitude, combinando recorrência mensal, escalabilidade por porte da operação e futuras linhas complementares de receita.
