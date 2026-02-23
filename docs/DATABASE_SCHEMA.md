# DATABASE SCHEMA — CannabIA

> **Banco de Dados:** PostgreSQL (gerenciado via Render)
> **Migration:** `migrations/001_initial_schema.sql`
> **Driver:** `psycopg2`

---

## Visão Geral da Arquitetura

O banco de dados segue uma arquitetura **multi-tenant leve** baseada em `clinic_id`. Não há schemas separados por tenant — o isolamento é garantido por filtros obrigatórios em todas as queries que envolvem dados sensíveis de pacientes.

```
┌─────────────────────────────────────────────────────────┐
│                    TABELAS GLOBAIS                       │
│   clinics        users        ai_prompt_versions        │
└────────────┬────────────────────┬───────────────────────┘
             │                    │
             └──── user_clinics ──┘  (tabela de ligação N:N)
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│              TABELAS TENANTADAS (por clinic_id)          │
│  patients  appointments  ai_audit_logs  alerts          │
│  medical_history  monitoring  treatment_plans           │
│  incoming_messages  message_status_updates              │
└─────────────────────────────────────────────────────────┘
```

---

## Tabelas Globais

Estas tabelas existem em escopo global. Um usuário pode pertencer a múltiplas clínicas.

### `clinics`

Cadastra as clínicas do sistema. Cada clínica é identificada por um `slug` único.

| Coluna       | Tipo          | Restrições                        | Descrição                     |
|--------------|---------------|-----------------------------------|-------------------------------|
| `id`         | `SERIAL`      | `PRIMARY KEY`                     | Identificador auto-incremento |
| `name`       | `VARCHAR(255)` | `NOT NULL`                       | Nome exibido da clínica       |
| `slug`       | `VARCHAR(64)` | `NOT NULL UNIQUE`                 | Chave de URL amigável         |
| `is_active`  | `BOOLEAN`     | `NOT NULL DEFAULT TRUE`           | Habilita/desabilita a clínica |
| `created_at` | `TIMESTAMP`   | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Data de criação            |
| `updated_at` | `TIMESTAMP`   | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Data de atualização        |

**Seed inicial:**
```sql
INSERT INTO clinics (name, slug, is_active)
VALUES ('Clínica Cannabia', 'cannabia', TRUE)
ON CONFLICT (slug) DO NOTHING;
```

---

### `users`

Cadastro de usuários (médicos, administradores). A autenticação usa `bcrypt` para armazenar o hash da senha.

| Coluna          | Tipo          | Restrições                           | Descrição                        |
|-----------------|---------------|--------------------------------------|----------------------------------|
| `id`            | `SERIAL`      | `PRIMARY KEY`                        | Identificador auto-incremento    |
| `username`      | `VARCHAR(50)` | `NOT NULL UNIQUE`                    | Login único do usuário           |
| `password_hash` | `VARCHAR(255)` | `NOT NULL`                          | Hash bcrypt da senha             |
| `role`          | `VARCHAR(20)` | `NOT NULL DEFAULT 'Medico'`          | Papel global: `Medico`, `Admin`  |
| `is_active`     | `BOOLEAN`     | `DEFAULT TRUE`                       | Permite desativar sem deletar    |
| `created_at`    | `TIMESTAMP`   | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Data de criação                  |

> **Atenção:** A coluna `role` aqui é o papel global do usuário. O papel dentro de cada clínica é definido em `user_clinics.role`.

---

### `ai_prompt_versions`

Controle de versão dos prompts de IA. Permite rastrear qual versão de prompt gerou cada resultado.

| Coluna        | Tipo          | Restrições                           | Descrição                           |
|---------------|---------------|--------------------------------------|-------------------------------------|
| `id`          | `SERIAL`      | `PRIMARY KEY`                        | Identificador                       |
| `name`        | `VARCHAR(50)` | `NOT NULL`                           | Nome do prompt (ex: `anamnese`)     |
| `version`     | `VARCHAR(50)` | `NOT NULL`                           | Versão semântica (ex: `v1.0`)       |
| `prompt_text` | `TEXT`        | `NOT NULL`                           | Texto completo do prompt            |
| `hash`        | `VARCHAR(64)` | `NOT NULL`                           | SHA-256 do prompt_text              |
| `active`      | `BOOLEAN`     | `DEFAULT TRUE`                       | Indica se é a versão ativa          |
| `created_at`  | `TIMESTAMP`   | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Data de criação                     |

---

### `user_clinics` — Tabela de Ligação (Multi-Tenancy)

Relacionamento N:N entre usuários e clínicas. **Esta é a peça central do modelo multi-tenant.**

| Coluna       | Tipo          | Restrições                           | Descrição                                   |
|--------------|---------------|--------------------------------------|---------------------------------------------|
| `user_id`    | `INT`         | `NOT NULL`                           | FK para `users.id`                          |
| `clinic_id`  | `INT`         | `NOT NULL`                           | FK para `clinics.id`                        |
| `role`       | `VARCHAR(50)` | `NOT NULL`                           | Papel nesta clínica: `clinic_admin`, `medico` |
| `is_default` | `BOOLEAN`     | `NOT NULL DEFAULT FALSE`             | Clínica padrão ao fazer login               |
| `created_at` | `TIMESTAMP`   | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Data de associação                          |
| **PK**       | `(user_id, clinic_id)` | `PRIMARY KEY`                 | Chave composta                              |

---

## Tabelas Tenantadas

Todas as tabelas abaixo possuem o campo `clinic_id INT NOT NULL`, que é o pilar do isolamento de dados entre clínicas. **Jamais faça SELECT nessas tabelas sem filtrar por `clinic_id`.**

---

### `patients`

Pacientes pertencentes a uma clínica.

| Coluna       | Tipo           | Restrições                              |
|--------------|----------------|-----------------------------------------|
| `id`         | `SERIAL`       | `PRIMARY KEY`                           |
| `clinic_id`  | `INT`          | `NOT NULL DEFAULT 1`                    |
| `name`       | `VARCHAR(100)` | `NOT NULL`                              |
| `email`      | `VARCHAR(100)` | `DEFAULT NULL`                          |
| `phone`      | `VARCHAR(20)`  | `DEFAULT NULL`                          |
| `created_at` | `TIMESTAMP`    | `NOT NULL DEFAULT CURRENT_TIMESTAMP`    |

---

### `ai_audit_logs`

**A tabela mais crítica do sistema.** Registra cada chamada à IA com payload completo (entrada/saída), tokens consumidos, custo estimado e rastreabilidade por `request_id`.

| Coluna              | Tipo            | Descrição                                          |
|---------------------|-----------------|----------------------------------------------------|
| `id`                | `SERIAL PK`     | Identificador                                      |
| `patient_id`        | `INT`           | Paciente associado                                 |
| `clinic_id`         | `INT`           | Clínica (isolamento multi-tenant)                  |
| `request_id`        | `VARCHAR(36)`   | UUID da requisição HTTP (rastreabilidade)          |
| `user_id`           | `VARCHAR(50)`   | ID do usuário que disparou a ação                  |
| `endpoint`          | `VARCHAR(100)`  | Rota da API chamada                                |
| `input_payload`     | `JSONB`         | Dados de entrada enviados à IA                     |
| `output_payload`    | `JSONB`         | Resposta completa da IA                            |
| `status`            | `VARCHAR(20)`   | `success`, `error`, `validation_error`, `security_blocked` |
| `error_message`     | `TEXT`          | Mensagem de erro, se houver                        |
| `model`             | `VARCHAR(50)`   | Modelo usado (ex: `gpt-4o-mini`)                   |
| `prompt_version`    | `VARCHAR(50)`   | Versão do prompt (ex: `v1.0`)                      |
| `prompt_hash`       | `VARCHAR(64)`   | SHA-256 do prompt (auditoria de integridade)       |
| `input_tokens`      | `INT`           | Tokens de entrada consumidos                       |
| `output_tokens`     | `INT`           | Tokens de saída gerados                            |
| `total_tokens`      | `INT`           | Total de tokens                                    |
| `clinical_time_ms`  | `INT`           | Tempo da etapa de análise clínica                  |
| `treatment_time_ms` | `INT`           | Tempo da etapa de plano terapêutico                |
| `report_time_ms`    | `INT`           | Tempo da etapa de geração de relatório             |
| `total_time_ms`     | `INT`           | Tempo total de processamento                       |
| `estimated_cost_usd`| `DECIMAL(10,6)` | Custo estimado em USD                              |
| `created_at`        | `TIMESTAMP`     | Data/hora do registro                              |

> **Nota:** Os campos `input_payload` e `output_payload` usam o tipo `JSONB` nativo do PostgreSQL, que permite indexação e queries avançadas.

---

### `appointments`

Agendamentos de consultas.

| Coluna             | Tipo          | Restrições                           |
|--------------------|---------------|--------------------------------------|
| `id`               | `SERIAL PK`   |                                      |
| `clinic_id`        | `INT`         | `NOT NULL DEFAULT 1`                 |
| `patient_id`       | `INT`         | `NOT NULL`                           |
| `appointment_date` | `TIMESTAMP`   | `NOT NULL`                           |
| `status`           | `VARCHAR(50)` | `DEFAULT NULL`                       |
| `created_at`       | `TIMESTAMP`   | `NOT NULL DEFAULT CURRENT_TIMESTAMP` |

---

### `incoming_messages`

Mensagens recebidas via webhook do WhatsApp.

| Coluna         | Tipo           |
|----------------|----------------|
| `id`           | `SERIAL PK`    |
| `clinic_id`    | `INT NOT NULL` |
| `sender`       | `VARCHAR(50)`  |
| `contact_name` | `VARCHAR(100)` |
| `message_text` | `TEXT`         |
| `timestamp`    | `VARCHAR(50)`  |

---

### `message_status_updates`

Atualizações de status das mensagens do WhatsApp (enviada, lida, entregue).

| Coluna       | Tipo            |
|--------------|-----------------|
| `id`         | `SERIAL PK`     |
| `clinic_id`  | `INT NOT NULL`  |
| `message_id` | `VARCHAR(100)`  |
| `status`     | `VARCHAR(50)`   |
| `timestamp`  | `VARCHAR(50)`   |
| `created_at` | `TIMESTAMP`     |

---

### `alerts`, `medical_history`, `monitoring`, `treatment_plans`

Tabelas auxiliares de suporte clínico, todas tenantadas com `clinic_id`.

| Tabela              | Propósito                                          |
|---------------------|----------------------------------------------------|
| `alerts`            | Alertas gerados pelo sistema para a clínica        |
| `medical_history`   | Histórico médico textual do paciente               |
| `monitoring`        | Registros de monitoramento e acompanhamento        |
| `treatment_plans`   | Planos de tratamento gerados ou aprovados          |

---

### `scientific_references`

Tabela global (sem `clinic_id`) para armazenar referências científicas usadas pela IA nas recomendações.

| Coluna             | Tipo           |
|--------------------|----------------|
| `id`               | `SERIAL PK`    |
| `reference_title`  | `VARCHAR(255)` |
| `reference_url`    | `VARCHAR(255)` |
| `created_at`       | `TIMESTAMP`    |

---

## Dados Iniciais (Seeds)

O arquivo `001_initial_schema.sql` insere automaticamente os dados mínimos para o sistema funcionar:

```sql
-- Clínica padrão
INSERT INTO clinics (name, slug, is_active)
VALUES ('Clínica Cannabia', 'cannabia', TRUE)
ON CONFLICT (slug) DO NOTHING;

-- Usuário admin padrão
INSERT INTO users (username, password_hash, role, is_active)
VALUES ('admin', '<bcrypt_hash>', 'Medico', TRUE)
ON CONFLICT (username) DO NOTHING;

-- Vínculo admin → clínica
INSERT INTO user_clinics (user_id, clinic_id, role, is_default)
VALUES (1, 1, 'clinic_admin', TRUE)
ON CONFLICT DO NOTHING;
```

> **Importante:** O `password_hash` no arquivo SQL é apenas um placeholder. Para produção, use o script `create_admin.py` para gerar um hash bcrypt real com uma senha segura.
