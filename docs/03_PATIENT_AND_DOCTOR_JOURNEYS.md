# 03 — Jornadas do Paciente e do Médico

## 1. Propósito do documento

Este documento define as **jornadas operacionais centrais** da plataforma CannabIA: o fluxo ponta a ponta do paciente e o fluxo ponta a ponta do médico.

Serve como base para desenho funcional dos módulos, modelagem de estados e eventos, construção de automações e desenho da experiência do usuário.

---

## 2. Princípios das jornadas

| Princípio | Descrição |
|-----------|-----------|
| **Jornada híbrida** | Automação, agentes operacionais e decisão clínica humana combinados |
| **Omnichannel** | Entrada e relacionamento por múltiplos canais (WhatsApp, web, PWA, app) |
| **Automação com supervisão** | A plataforma automatiza coleta e organização; humano intervém quando necessário |
| **Médico como decisor final** | Toda decisão clínica relevante permanece com o médico |
| **Acompanhamento longitudinal** | A jornada não termina na consulta |
| **White-label por tenant** | Cada jornada é operada na marca, canais e regras do tenant |

---

## 3. Canais de entrada do paciente

- Página web
- Botão de WhatsApp (**canal prioritário**)
- PWA (Progressive Web App)
- Aplicativo Android
- Aplicativo iOS
- Webchat

---

## 4. Jornada completa do paciente

### Etapa 1 — Entrada no canal
O paciente acessa um dos canais habilitados pelo tenant.

**Eventos gerados:** início de atendimento, identificação do canal, criação de lead, associação ao tenant.

---

### Etapa 2 — Acolhimento e esclarecimento inicial
O agente apresenta informações sobre o tratamento, esclarece dúvidas e qualifica a intenção.

**Responsável:** agente de atendimento (automatizado com transbordo para humano)

**Resultados possíveis:**
- Paciente segue para triagem
- Paciente solicita atendimento humano
- Paciente interrompe a jornada
- Paciente decide agendar consulta

---

### Etapa 3 — Triagem inicial
O sistema identifica a necessidade do paciente.

**Informações coletadas:**
- Queixa principal e área de interesse
- Sintomas iniciais e condição relatada
- Tipo de atendimento desejado
- Nível de maturidade sobre o tratamento

**Responsável:** agente de atendimento, fluxo automatizado, humano quando necessário.

---

### Etapa 4 — Anamnese assistida
Coleta estruturada de informações clínicas e operacionais.

**Conteúdo da anamnese:**
- Identificação e histórico do paciente
- Sintomas, queixas e medicações em uso
- Alergias e exames já realizados
- Contexto terapêutico

**Responsável:** sistema com apoio de IA; paciente fornece informações; agente auxilia quando necessário.

**Eventos gerados:** início da anamnese, conclusão parcial, conclusão final, dados estruturados do caso.

---

### Etapa 5 — Envio de exames e documentos
O paciente envia documentos existentes pelo canal conversacional.

**Tipos de conteúdo:**
- Exames laboratoriais e de imagem
- Documentos médicos e prescrições prévias
- Arquivos digitalizados

**Eventos gerados:** arquivo recebido, documento vinculado ao paciente.

---

### Etapa 6 — Criação de cadastro e vínculo com tenant
O paciente passa de lead a registro formal na base da plataforma.

**Resultados:** conta criada, paciente identificado, timeline aberta, caso vinculado ao tenant.

---

### Etapa 7 — Indicação de especialista
Com base na anamnese, o sistema identifica o médico mais adequado.

**Critérios:** especialidade, disponibilidade, vínculo com tenant, regras da clínica/associação.

---

### Etapa 8 — Aceite comercial
O paciente manifesta interesse em seguir para consulta.

**Eventos gerados:** aceite da consulta, preparação do pagamento.

---

### Etapa 9 — Pagamento via QR Code
A plataforma gera e envia QR Code para pagamento da consulta.

**Estados do pagamento:**
- Pendente
- Confirmado
- Expirado
- Com erro

**Eventos gerados:** QR Code emitido, cobrança criada, pagamento confirmado/expirado/com falha.

---

### Etapa 10 — Confirmação e agendamento
Após confirmação do pagamento, a consulta é agendada.

**Eventos gerados:** consulta criada, paciente notificado, médico notificado, agenda atualizada.

---

### Etapa 11 — Lembretes automáticos
A plataforma dispara lembretes para reduzir faltas.

**Lembretes aprovados:**
- 24 horas antes — para paciente e médico
- 1 hora antes — para paciente e médico

---

### Etapa 12 — Preparação pré-consulta
Antes da consulta, a plataforma estrutura o caso para o médico.

**Componentes:**
- Anamnese consolidada e documentos recebidos
- Busca científica contextual (RAG + PubMed)
- Relatório de apoio com evidências
- Sugestões informacionais de dose e proporção de canabinoides

**Responsável:** sistema, IA, motor de busca científica, banco vetorial.

---

### Etapa 13 — Consulta médica
O médico avalia o caso, toma decisões clínicas, define conduta e solicita exames se necessário.

**Eventos gerados:** consulta realizada, consulta não realizada (falta), conduta registrada.

---

### Etapa 14 — Registro em prontuário
As decisões e observações passam a integrar o prontuário longitudinal.

**Conteúdo registrado:** anamnese, observações médicas, conduta, exames solicitados, plano terapêutico, acompanhamento programado.

---

### Etapa 15 — Acompanhamento contínuo
O paciente entra em fluxo ativo de acompanhamento pós-consulta.

**Componentes:** questionários semanais, monitoramento de adesão, detecção de sinais de alerta.

**Responsável:** agente de acompanhamento, sistema, paciente.

---

### Etapa 16 — Geração de alertas e retorno
Respostas e sinais do acompanhamento disparam alertas e possíveis revisões.

**Desdobramentos possíveis:**
- Manutenção do acompanhamento
- Ajuste de dose ou retorno médico
- Solicitação de novos exames
- Acionamento do médico

---

## 5. Jornada completa do médico

### Etapa 1 — Recebimento do caso preparado
**Conteúdo recebido:**
- Anamnese organizada e histórico disponível
- Exames e documentos anexados
- Relatório científico contextual (evidências, doses, canabinoides)
- Apoio informacional terapêutico

---

### Etapa 2 — Revisão clínica pré-consulta
O médico analisa o material preparado para chegar à consulta com contexto consolidado.

---

### Etapa 3 — Consulta e decisão clínica
O médico ouve o paciente, valida as informações e toma a decisão clínica final.

> **Princípio obrigatório:** a IA pode sugerir e organizar, mas a decisão clínica é exclusivamente humana.

---

### Etapa 4 — Registro da consulta
O médico formaliza:
- Observações e conduta
- Plano terapêutico e exames solicitados
- Ajustes clínicos, orientações e plano de acompanhamento

---

### Etapa 5 — Definição do acompanhamento
O médico define:
- Frequência esperada de acompanhamento
- Pontos de atenção e sinais que exigem retorno
- Necessidade de revisão ou novo exame

---

### Etapa 6 — Recebimento de relatórios e alertas
O médico recebe:
- Respostas de questionários e relatórios consolidados
- Alertas de piora ou suspeita de baixa adesão
- Necessidade de reavaliação

---

### Etapa 7 — Ajuste e retorno
Com base nos alertas, o médico decide:
- Manter conduta
- Ajustar dose ou redefinir tratamento
- Pedir retorno ou novos exames

---

## 6. Pontos de automação na jornada

A plataforma deve automatizar preferencialmente:

- Acolhimento inicial e coleta de dados
- Criação de cadastro do paciente
- Emissão de QR Code e confirmação de pagamento
- Agendamento e notificações
- Lembretes de consulta
- Preparação pré-consulta (anamnese + busca científica)
- Envio de questionários de acompanhamento
- Classificação inicial das respostas
- Geração de alertas e atualização de timeline

---

## 7. Pontos de transbordo para humano

| Situação | Ação |
|---------|------|
| Dúvida complexa do paciente | Agente humano |
| Solicitação expressa | Agente humano |
| Sensibilidade emocional | Agente humano |
| Falha no pagamento | Operação do tenant |
| Inconsistência documental | Operação do tenant |
| Suspeita de risco clínico | Médico |
| Necessidade de decisão médica | Médico |

---

## 8. Responsáveis por etapa (resumo)

| Responsável | Etapas |
|-------------|--------|
| **Agente de atendimento** | Entrada, acolhimento, triagem, coleta, pagamento, agendamento |
| **Agente de acompanhamento** | Questionários, monitoramento, alertas, sustentação longitudinal |
| **Médico** | Validação clínica, consulta, conduta, prontuário, alertas, ajustes |
| **Paciente** | Dados, documentos, respostas, comparecimento, adesão |
| **Admin do Tenant** | Configuração, agenda, equipe, canais, supervisão administrativa |

---

## 9. Estados da jornada do paciente

```
lead_criado → acolhimento_em_andamento → triagem_em_andamento
→ anamnese_em_andamento → aguardando_documentos → aguardando_aceite
→ aguardando_pagamento → pagamento_confirmado → aguardando_consulta
→ consulta_realizada → em_acompanhamento → alerta_ativo
→ aguardando_retorno → jornada_encerrada | jornada_pausada
```

---

## 10. Estados da jornada do médico

```
caso_recebido → caso_em_revisao → consulta_agendada
→ consulta_realizada → conduta_registrada → acompanhamento_definido
→ alerta_pendente → alerta_revisado → retorno_solicitado → caso_em_monitoramento
```

---

## 11. Eventos críticos auditáveis

A plataforma deve registrar como eventos auditáveis, no mínimo:

```
primeiro_contato_iniciado, triagem_concluida, anamnese_concluida,
documento_recebido, paciente_cadastrado, especialista_indicado,
qr_code_emitido, pagamento_confirmado, pagamento_expirado,
consulta_agendada, lembrete_enviado, consulta_realizada,
ausencia_em_consulta, prontuario_atualizado, questionario_enviado,
questionario_respondido, alerta_gerado, alerta_escalado,
revisao_medica_solicitada, retorno_agendado
```

---

## 12. Implicações para produto e banco de dados

As jornadas descritas exigem suporte a:

- Estados de jornada e transições de estado
- Timeline do paciente e do médico
- Logs auditáveis de eventos operacionais
- Armazenamento de documentos e registros de pagamento
- Agenda e consulta formalizadas
- Prontuário longitudinal
- Fila de alertas e histórico de notificações
- Controle de responsável por etapa

---

## 13. Regras centrais aprovadas

- O paciente pode entrar por múltiplos canais; WhatsApp é canal prioritário
- A jornada começa com acolhimento e inclui anamnese antes da consulta
- O paciente pode enviar exames e documentos antes da consulta
- A conta do paciente é criada durante a jornada inicial
- A consulta depende de aceite e pagamento confirmado
- O QR Code é parte do fluxo de pagamento
- A plataforma prepara o caso cientificamente antes da consulta
- O médico decide e registra a conduta
- O paciente entra em acompanhamento contínuo após a consulta
- Questionários semanais são o gatilho inicial do acompanhamento
- A jornada deve ser auditável ponta a ponta

---

## 14. Conclusão

A CannabIA deve operar jornadas completas e contínuas, integrando acolhimento, triagem, anamnese, preparação científica, consulta, prontuário e acompanhamento.

O diferencial do produto não está apenas na consulta médica, mas na capacidade de estruturar e sustentar a jornada do paciente com apoio operacional, inteligência, automação e supervisão clínica.
