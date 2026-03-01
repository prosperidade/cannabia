# WHATSAPP FLOW - CannabIA

Este documento detalha o fluxo operacional de ponta-a-ponta de conversação e gerenciamento de estados no WhatsApp, utilizando a API Oficial da Meta (WhatsApp Business API).

## 1. Conexão e Verificação do Webhook (Meta)
Para que o sistema passe a receber mensagens, a Meta envia um desafio inicial (GET request).
- A aplicação (`src/web/routes/realtime_notifications.py`) verifica se o modo é `subscribe` e o token enviado corresponde ao `VERIFY_TOKEN` configurado no `.env`.
- Caso válido, o servidor devolve o `challenge` em texto puro, efetivando a conexão.

## 2. Recebimento da Mensagem (POST /webhook/meta)
Quando um paciente envia "Olá" ou responde a uma anamnese:
1. **Verificação de Carga e Autenticidade (Segurança Máxima):** O Payload da Meta é avaliado. O servidor checa limites de tamanho (`MAX_CONTENT_LENGTH`) e rate limit (`WEBHOOK_RATE_LIMIT`) contra sobrecargas (DDoS/spam).
2. **Assinatura HMAC-SHA256:** A carga bruta (`raw_body`) é criptografada em *runtime* com o `WHATSAPP_APP_SECRET`. Se bater com o `X-Hub-Signature-256`, o remetente é genuíno.

## 3. Identificação e Processamento de Tenancy
1. **Isolamento de Clínica (`clinic_id`):** O número de entrada e os metadados da rota estabelecem de qual clínica a mensagem se origina. (Normalmente amarrado no `DEFAULT_CLINIC_ID` em caso de single-number para multi-tenant, ou webhooks roteados por path).
2. **Despacho Assíncrono:** O payload validado (agora parseado como JSON) é remetido aos "handlers" de negócio, através da função `_process_meta_payload`.

## 4. O Handler Principal: Estado e Anamnese (`handle_message_event`)
Aqui reside o cérebro conversacional:
1. **Persistência do Evento:** A mensagem original é salva na tabela `incoming_messages` para auditoria do médico (`sender`, `contact_name`, e `message_text`).
2. **Atualização do Dashboard em Tempo Real:** Uma chamada WebSockets (`socketio.emit`) dispara os dados recém-chegados para a tela da clínica, permitindo visualização imediata pelos atendentes/médicos.
3. **Gerenciamento do Paciente:** O sistema checa se o remetente (`phone`) já existe na base de `patients` daquele `clinic_id`. Se não, ele é automaticamente criado.
4. **Acionamento da IA:**
   - Se for uma resposta contextual de Anamnese, o pipeline de serviço (`src/ai/service.py`) é ativado.
   - Os dados são validados (Pydantic models) para garantir integridade médica (`AnamnesisInput`).
   - A requisição passa por verificações de Prompt Injection (anti-fraude) antes de prosseguir à IA (`gpt-4o-mini`).

## 5. Resposta ao Paciente
Após o processamento dos dados, o bot necessita dar um retorno ativo (feedback/pergunta seguinte):
- O módulo `src/integrations/whatsapp.py` entra em ação.
- Ele possui suporte a mensagens de texto plano (dentro da janela de 24 horas permitida pela Meta para conversações ativas) ou envio de templates pré-aprovados (para reinício de conversas, agendamentos, envios de boletos/pdf).
- Utiliza um cabeçalho HTTP de `Authorization: Bearer` com a `META_WHATSAPP_KEY` do ambiente, enviando um JSON padronizado com `messaging_product: whatsapp`.

## 6. Confirmação e Tracking de Entrega
A Meta não envia apenas mensagens de texto. Sempre que o bot (ou o médico) envia algo, o WhatsApp dispara eventos de status:
- O mesmo webhook recebe notificações (`message_template_status_update`) de que a mensagem foi entregue (`delivered`) ou lida (`read`).
- O handler `handle_status_event` captura a identificação (`message_id`) e loga a atualização na tabela `message_status_updates`, refletindo o duplo-tique-azul no dashboard da clínica em tempo real.