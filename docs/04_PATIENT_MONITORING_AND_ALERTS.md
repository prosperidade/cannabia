# 04 — Acompanhamento do Paciente e Alertas

## 1. Propósito do documento

Este documento define o **modelo de acompanhamento contínuo do paciente** dentro da plataforma CannabIA: frequência, questionários, classificação de sinais, gatilhos clínico-operacionais, geração de alertas e política de escalonamento.

---

## 2. Visão geral do acompanhamento

O acompanhamento do paciente é parte central da proposta de valor da CannabIA. A plataforma não se limita ao momento da consulta: após a definição da conduta médica, o paciente entra em **fluxo contínuo assistido**, com suporte de agentes, automação e supervisão clínica.

**Objetivos do acompanhamento:**

- Melhorar adesão terapêutica
- Monitorar resposta ao tratamento
- Identificar efeitos adversos precocemente
- Antecipar necessidade de ajuste
- Organizar revisões e retornos
- Sustentar relacionamento longitudinal com o paciente

---

## 3. Natureza do acompanhamento

O acompanhamento será **híbrido**:

| Componente | Responsável |
|-----------|-------------|
| Coleta automatizada via questionários | Sistema |
| Classificação inicial de respostas | Sistema (regras + IA) |
| Geração de alertas | Sistema |
| Contato ativo com o paciente | Agente de acompanhamento |
| Decisão clínica sobre alertas | Médico |

> A automação organiza e sinaliza. A interpretação e decisão clínica final permanecem com o médico.

---

## 4. Frequência inicial

**Frequência aprovada para a primeira fase: questionários semanais.**

Essa frequência poderá variar futuramente conforme: protocolo clínico, fase do tratamento, resposta terapêutica, orientação do médico ou regras do tenant.

---

## 5. Campos mínimos dos questionários semanais

| Campo | Descrição |
|-------|-----------|
| Intensidade dos sintomas | Escala de percepção |
| Evolução desde a última interação | Melhora / estável / piora |
| Adesão ao tratamento | Regularidade de uso |
| Efeitos colaterais | Tipo e intensidade |
| Qualidade do sono | Escala subjetiva |
| Dor | Escala numérica |
| Ansiedade | Escala subjetiva |
| Apetite | Escala subjetiva |
| Bem-estar geral | Percepção global |
| Dificuldades no uso | Dose, acesso, compreensão |
| Relato livre | Campo aberto |

---

## 6. Classificação de severidade

Toda resposta recebida gera uma classificação inicial de severidade em quatro níveis:

### 🟢 Verde — Estabilidade

**Situações típicas:** sintomas estáveis, melhora percebida, boa adesão, ausência de efeitos adversos.

**Ação:** manter fluxo normal de acompanhamento.

---

### 🟡 Amarelo — Atenção moderada

**Situações típicas:** leve piora, adesão inconsistente, desconforto leve, dúvida recorrente, resposta pouco clara.

**Ação:** contato do agente, reforço de orientação, novo check-in antecipado.

---

### 🟠 Laranja — Revisão clínica necessária

**Situações típicas:** piora progressiva, efeito adverso moderado, falha importante de adesão, relato de dose inadequada, novo sintoma relevante.

**Ação:** agente registra contexto → alerta clínico gerado → caso encaminhado ao médico para avaliação.

---

### 🔴 Vermelho — Prioridade máxima

**Situações típicas:** piora aguda, evento adverso grave, sinal crítico definido em protocolo, risco clínico relevante, combinação de múltiplos sinais críticos.

**Ação:** alerta imediato → escalonamento prioritário ao médico → tentativa rápida de contato.

---

## 7. Gatilhos clínico-operacionais

Os gatilhos são regras que transformam resposta em ação. A plataforma deve calcular gatilhos com base em:

- Respostas objetivas e subjetivas
- Campos livres do paciente
- Ausência de resposta
- Repetição de padrão negativo
- Combinação de múltiplos sinais moderados

**Exemplos de gatilho:**

| Gatilho | Classificação |
|---------|--------------|
| 3 semanas sem melhora | Laranja |
| Piora relevante de dor | Laranja |
| Interrupção da dose prescrita | Laranja |
| Efeito colateral importante | Laranja |
| Nova queixa neurológica/psiquiátrica | Vermelho |
| Baixa adesão persistente | Amarelo → Laranja |

---

## 8. Ausência de resposta como sinal

A ausência de resposta também deve ser tratada como evento relevante:

| Situação | Ação |
|---------|------|
| 1 ausência | Lembrete automático |
| 2 ausências consecutivas | Ação do agente |
| 3 ausências consecutivas | Alerta operacional |
| Ausência com histórico delicado | Possível escalonamento clínico |

---

## 9. Política de escalonamento

O escalonamento será realizado em camadas progressivas:

| Nível | Responsável | Ativa para |
|-------|-------------|-----------|
| **1 — Automação** | Sistema | Todos os casos |
| **2 — Agente de acompanhamento** | Agente | Amarelos, laranjas operacionais, ausências |
| **3 — Médico** | Médico | Vermelhos, laranjas clínicos, ajuste terapêutico |

### Regras de progressão automática

- 3 amarelos consecutivos → pode virar laranja
- Combinação de múltiplos sinais moderados → pode virar laranja
- Laranja sem tratamento no prazo → sobe de prioridade
- Vermelho → sempre gera registro crítico

---

## 10. SLA inicial recomendado

| Nível | Prazo máximo de ação |
|-------|---------------------|
| 🟢 Verde | Rotina normal |
| 🟡 Amarelo | Até 24 horas |
| 🟠 Laranja | Até 4 horas úteis |
| 🔴 Vermelho | Imediato (prioridade máxima) |

---

## 11. Conteúdo mínimo de um alerta

```
paciente_id, tenant_id, medico_responsavel_id,
data_hora, origem_do_alerta, questionario_relacionado,
classificacao_severidade, motivo_do_alerta, score,
acao_sugerida, responsavel_atual, prazo_esperado,
status_do_alerta, historico_escalonamento, desfecho
```

---

## 12. Estados do alerta

```
gerado → em_triagem_operacional → aguardando_complemento
→ escalado_ao_medico → em_revisao_clinica → acao_definida
→ encerrado | expirado | reaberto
```

---

## 13. Timeline do acompanhamento

O acompanhamento deve ser visível em uma **timeline única do paciente**, contendo:

- Envio e resposta de questionário
- Classificação gerada
- Contato do agente e observações
- Alerta criado e escalado
- Ação médica e ajuste de tratamento
- Pedido de retorno ou exame

---

## 14. Responsáveis no acompanhamento

| Responsável | Atribuições |
|-------------|------------|
| **Sistema** | Enviar questionários, classificar respostas, gerar alertas, atualizar timeline |
| **Agente de acompanhamento** | Contato com paciente, contexto adicional, orientações não clínicas, encaminhamento |
| **Médico** | Revisar alertas clínicos, decidir ajuste/retorno/exames, redefinir conduta |
| **Paciente** | Responder questionários, informar evolução, relatar sintomas |

---

## 15. Regras aprovadas neste documento

- O acompanhamento do paciente será contínuo e longitudinal
- A frequência inicial será semanal
- O gatilho principal virá dos questionários
- Ausência de resposta também gera sinal
- Respostas serão classificadas em verde, amarelo, laranja e vermelho
- Haverá política de escalonamento por camadas
- SLA define prazo por nível de severidade
- Alertas serão auditáveis com estados rastreáveis
- A timeline do paciente registra todo o histórico de acompanhamento

---

## 16. Pontos para aprofundamento futuro

- Modelo final de score clínico por especialidade
- Protocolos por patologia ou perfil terapêutico
- Parametrização de gatilhos por tenant
- Regras regulatórias sobre urgência
- Integração com agenda para retorno automático
- Dashboards de acompanhamento e risco
- Mensagens automáticas por tipo de alerta

---

## 17. Conclusão

O acompanhamento contínuo é um dos principais diferenciais estratégicos da CannabIA. Ele transforma a plataforma em uma operação longitudinal — e não apenas em um sistema de consulta.

Ao estruturar questionários, classificação, alertas e escalonamento, a CannabIA cria condições para melhorar adesão, acelerar resposta clínica e sustentar uma jornada de cuidado assistida de ponta a ponta.
