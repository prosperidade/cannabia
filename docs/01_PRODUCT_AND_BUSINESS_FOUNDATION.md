# 01 — Fundação de Produto e Negócio

## 1. Propósito do documento

Este documento estabelece a **base estratégica, conceitual e operacional** da plataforma CannabIA, consolidando a visão do produto, o modelo de negócio inicial, os atores do ecossistema, as jornadas macro e o papel da inteligência artificial na operação.

Serve como **documento-mãe** para orientar arquitetura, módulos, banco de dados, fluxos do sistema e toda a documentação da plataforma.

---

## 2. Visão da plataforma

A CannabIA é uma **plataforma white-label de operação assistida** para o ecossistema de cannabis medicinal.

Ela não deve ser entendida apenas como um prontuário, nem apenas como um sistema de IA clínica. Sua proposta é mais ampla: entregar uma **infraestrutura digital completa** para que clínicas, associações e médicos possam operar atendimento, relacionamento, acompanhamento e suporte à decisão clínica como se a solução fosse própria.

A plataforma combina:

- Atendimento e acolhimento inicial por agentes
- Triagem e anamnese assistida por IA
- Organização do fluxo comercial e assistencial
- Apoio científico baseado em evidências (RAG + PubMed)
- Geração de relatórios preparatórios para consulta
- Prontuário clínico longitudinal
- Acompanhamento contínuo do paciente
- Alertas assistidos por regras e IA
- Operação white-label por tenant

---

## 3. Objetivo central do negócio

A CannabIA existe para atuar simultaneamente como:

- **Prontuário inteligente**
- **Motor de apoio à prescrição e decisão clínica**
- **CRM clínico e operacional**
- **Plataforma de jornada do paciente**
- **Canal de relacionamento e acompanhamento**
- **Infraestrutura white-label para parceiros**

Em termos práticos, a CannabIA permite que o tenant contratante opere uma jornada completa de cuidado e relacionamento com ganho de escala, padronização, inteligência operacional e apoio científico — mantendo o médico como **autoridade final da decisão clínica**.

---

## 4. Proposta de valor

### 4.1. Estrutura operacional pronta

A plataforma entrega ao cliente contratante uma operação digital estruturada para atendimento, triagem, anamnese, agendamento, pagamento, consulta e acompanhamento.

### 4.2. White-label real

Cada clínica, associação ou médico opera a plataforma com sua própria marca, canais e credenciais de integração, utilizando a infraestrutura central da CannabIA como se fosse um sistema próprio.

### 4.3. Apoio clínico-científico

A plataforma prepara o médico antes da consulta com anamnese organizada, exames enviados, busca científica contextual e sugestões de apoio — reduzindo tempo operacional e aumentando a qualidade da preparação.

### 4.4. Acompanhamento longitudinal

Após a consulta, o paciente continua em acompanhamento ativo com questionários, interações, alertas e reavaliações, permitindo maior aderência terapêutica e visibilidade clínica.

### 4.5. Escalabilidade comercial e assistencial

O modelo permite atender operações pequenas, médias e grandes com planos por volume e capacidade de expansão.

---

## 5. Organização do ecossistema

### 5.1. Organização-mãe

A organização-mãe é a própria operação da CannabIA. Ela é responsável por desenvolver e manter a plataforma, comercializar o sistema, governar o modelo white-label, definir planos e faturamento, controlar templates e fluxos globais, operar suporte e onboarding, administrar banners e monetização adicional.

A organização-mãe **não é o tenant** do atendimento final. Ela é a provedora da infraestrutura.

### 5.2. Tenants contratantes

Os tenants contratantes da plataforma são:

- **Clínicas**
- **Associações**
- **Médicos autônomos**

Cada tenant utiliza a CannabIA em modelo white-label, com identidade e operação próprias.

### 5.3. Lógica do modelo white-label

O tenant configurará, conforme escopo do plano:

- Marca e identidade visual
- Subdomínio próprio
- Número de WhatsApp
- E-mail operacional
- Chave de API da plataforma de IA
- Equipe, agenda e fluxos operacionais

---

## 6. Entidades principais do negócio

| Entidade | Papel |
|---------|-------|
| **Clínica** | Tenant contratante com múltiplos médicos vinculados |
| **Associação** | Tenant contratante com atendimento, relacionamento e encaminhamento |
| **Médico** | Responsável pela decisão clínica, prescrição e acompanhamento |
| **Agente de atendimento e acolhimento** | Contato inicial, triagem, captação, coleta, encaminhamento e transbordo para humano |
| **Agente de acompanhamento** | Monitoramento pós-consulta, questionários e escalonamento de alertas |
| **Paciente** | Usuário final da jornada de cuidado |

---

## 7. Fluxo macro do paciente

```
Entrada no canal
    → Acolhimento pelo agente
        → Triagem e anamnese assistida
            → Envio de exames e documentos
                → Cadastro criado no sistema
                    → Indicação de especialista
                        → Aceite + QR Code de pagamento
                            → Confirmação + agendamento
                                → Lembretes (24h e 1h antes)
                                    → Preparação científica pré-consulta
                                        → Consulta médica
                                            → Registro em prontuário
                                                → Acompanhamento contínuo semanal
                                                    → Alertas e retorno quando necessário
```

---

## 8. Fluxo macro do médico

```
Recebimento do caso preparado (anamnese + exames + relatório científico)
    → Revisão clínica pré-consulta
        → Consulta e decisão clínica
            → Registro em prontuário
                → Definição do acompanhamento
                    → Recebimento de relatórios e alertas
                        → Ajuste de dose / retorno / novos exames
```

---

## 9. Papel da IA no produto

### 9.1. Onde a IA ajuda

- Acolhimento e condução inicial
- Organização e estruturação da anamnese
- Apoio à triagem operacional
- Busca científica contextual
- Consolidação de relatórios preparatórios
- Classificação inicial de sinais de acompanhamento
- Automação de comunicação e lembretes

### 9.2. Onde a decisão deve ser humana

A decisão clínica **obrigatoriamente humana** inclui:

- Interpretação clínica final
- Definição de conduta e prescrição
- Ajuste terapêutico
- Validação de riscos
- Decisão sobre retorno, exames e mudanças de tratamento

> A plataforma deve deixar claro, sempre, que a IA atua como suporte e que a responsabilidade clínica final permanece com o profissional médico.

---

## 10. Papel do RAG e do banco vetorial

O RAG e banco vetorial sustentam o diferencial científico da plataforma. Seu papel inclui:

- Apoio à busca de evidências para o relatório pré-consulta
- Contextualização clínica por caso
- Suporte à geração de relatórios assistidos
- Base de conhecimento operacional futura
- Eventual apoio a respostas orientativas para equipe

---

## 11. Fontes de conhecimento pretendidas

- PubMed e literatura científica indexada
- Diretrizes clínicas
- Protocolos internos
- Artigos científicos curados
- Materiais regulatórios
- Conteúdos produzidos por associações parceiras
- Histórico anonimizado (quando juridicamente permitido)

---

## 12. Modelo de monetização inicial

### Receita principal

Assinatura mensal recorrente paga por clínica, associação ou médico, diferenciada por volume de pacientes:

| Plano | Perfil |
|-------|--------|
| **Basic** | Até 100 pacientes ativos |
| **Pro** | 101 a 500 pacientes ativos |
| **Premium** | Ilimitado |

### Custos de IA

A chave de API da plataforma de IA será configurada pelo próprio tenant na fase inicial, reduzindo o custo direto da CannabIA.

### Receita complementar

- Banners e mídia da indústria farmacêutica
- Serviços de implantação, setup e customização
- Futuras comissões de vendas

---

## 13. Premissas estruturais aprovadas

- A CannabIA será uma plataforma white-label
- A organização-mãe é a própria operação da CannabIA
- Os tenants contratantes serão clínica, associação e médico
- A plataforma entregará estrutura completa de atendimento, consulta e acompanhamento
- O médico é o responsável final pela decisão clínica
- A IA apoia, organiza e acelera — mas não substitui a autoridade médica
- Haverá agentes de atendimento e agentes de acompanhamento
- Haverá possibilidade de transbordo para humano
- O acompanhamento inicial será guiado por questionários semanais
- O tenant poderá configurar canais e integrações, incluindo WhatsApp, e-mail e chave de API
- O modelo comercial será recorrente, por planos, com monetização complementar por mídia

---

## 14. Pontos ainda a detalhar

- Regras formais de vínculo entre médico, clínica e associação
- Permissões detalhadas por perfil
- Critérios objetivos de cada plano comercial
- Matriz de gatilhos clínicos
- Política de escalonamento de alertas
- Governança do banco de conhecimento
- Política de pagamentos, QR Code e validações
- Regras de prontuário, consentimento e compartilhamento de dados
- Requisitos regulatórios e jurídicos específicos

---

## 15. Conclusão

A CannabIA deve ser documentada e construída como uma **infraestrutura operacional, clínica, científica e comercial** para o ecossistema de cannabis medicinal.

Sua identidade de produto está definida como uma plataforma white-label capaz de sustentar a jornada completa do paciente e a operação dos parceiros contratantes, unindo atendimento, prontuário, apoio científico, IA assistiva, acompanhamento e escalabilidade.

Este documento é a fundação sobre a qual serão construídos todos os demais documentos de arquitetura, banco de dados, fluxos, módulos, integrações, operação e governança.
