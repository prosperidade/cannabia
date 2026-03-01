# DATABASE MAPPING - CannabIA

Este documento mapeia o esquema completo do banco de dados relacional (PostgreSQL) utilizado no projeto CannabIA, documentado no `migrations/001_initial_schema.sql`.

## Estrutura Multi-Tenant Base (Clínicas e Usuários)
Toda a plataforma (pacientes, consultas e dados clínicos) gira em torno do `clinic_id`, o isolamento primário. Jamais faça SELECTs nas tabelas de Tenant sem filtrar por essa chave.

### Tabela `clinics`
Clínicas cadastradas no sistema.
- `id` (SERIAL PRIMARY KEY)
- `name` (VARCHAR): Nome oficial.
- `slug` (VARCHAR): Nome curto e único, utilizado para login ou URL.
- `is_active` (BOOLEAN): Define se a clínica está operante.

### Tabela `users` e `user_clinics`
Usuários do sistema (médicos, administradores). O relacionamento é N:N, ou seja, um médico pode atender em mais de uma clínica.
- `users`: Armazena o `username`, a `password_hash` bcrypt e a `role` global do usuário.
- `user_clinics`: A tabela pivot, que armazena a `role` específica (ex: `clinic_admin`, `medico`) do usuário numa determinada `clinic_id`. Possui a coluna `is_default` para definir qual a clínica primária do profissional.

## Dados Médicos e Pacientes (Tenants)

### Tabela `patients`
Cadastro básico dos pacientes, alimentado pelo WhatsApp no momento de um novo atendimento.
- `id` (SERIAL PRIMARY KEY)
- `clinic_id` (INT): Chave da clínica.
- `name` (VARCHAR)
- `email` (VARCHAR)
- `phone` (VARCHAR): Identificador chave (número de WhatsApp).

### Tabela `medical_history`
Armazena informações densas da anamnese. O bot do WhatsApp coleta e organiza em blocos narrativos que alimentam a IA.
- `id` (SERIAL PRIMARY KEY)
- `clinic_id` (INT) e `patient_id` (INT)
- `history` (TEXT): Bloco consolidado do histórico clínico.

### Tabela `treatment_plans`
Armazena a conduta gerada e aprovada pelo médico baseada no histórico. É a entrada primordial para o relatório científico (RAG).
- `id` (SERIAL PRIMARY KEY)
- `clinic_id` (INT) e `patient_id` (INT)
- `plan_description` (TEXT): Reúne proporções sugeridas (CBD/THC), posologia, via de administração e escalonamento terapêutico.

### Tabela `appointments`
Sistema de agendamento integrado.
- `id` (SERIAL PRIMARY KEY)
- `clinic_id` (INT) e `patient_id` (INT)
- `appointment_date` (TIMESTAMP) e `status` (VARCHAR).

## Integração de WhatsApp e Monitoramento

### Tabela `incoming_messages` e `message_status_updates`
Gerenciamento de webhook da Meta e histórico temporal.
- `incoming_messages`: Guarda os dados brutos como `sender`, `contact_name` e `message_text`.
- `message_status_updates`: Confirmações de envio (enviada, lida, entregue).

### Tabelas `alerts` e `monitoring`
Controle clínico de longo prazo.
- `alerts`: Armazena as mensagens proativas geradas para follow-ups ou urgências identificadas nos retornos do paciente.
- `monitoring`: Campos de `status` e `notes` com a evolução do paciente ao longo do tratamento.

## Engenharia de Prompt, RAG e Auditoria

### Tabela `ai_prompt_versions`
Garante a reprodutibilidade. Permite rastrear exatamente a qual versão do sistema pertencia um prompt (text) utilizado, utilizando `version` e `hash` SHA-256.

### Tabela `scientific_references`
Tabela global, não-tenantada. Cadastra as fontes e artigos científicos base que servirão como evidências externas.
- `id` (SERIAL PRIMARY KEY)
- `reference_title` (VARCHAR)
- `reference_url` (VARCHAR)

### Tabela `ai_audit_logs` (A Peça Central de Custos e Rastreio)
Responsável por garantir segurança jurídica e transparência operacional na IA.
- `id` (SERIAL PRIMARY KEY)
- `patient_id` (INT) e `clinic_id` (INT)
- `request_id` (VARCHAR): ID único da requisição (gerado via Flask middleware).
- `input_payload` e `output_payload` (JSONB): *Os dados da requisição (prompt enviado, resultado integral do OpenAI e do Gemini), indexáveis e facilmente consultáveis no PostgreSQL.*
- `status` (VARCHAR): Ex: `success`, `error`, `security_blocked` (para Prompt Injection).
- `model`, `prompt_version`, `prompt_hash`.
- *Metricas e Custos*: `input_tokens`, `output_tokens`, tempos em milissegundos das etapas de análise clínica, de plano de tratamento e de geração de relatórios, além do `estimated_cost_usd` (custo direto em dólar por requisição na OpenAI API e Gemini API).