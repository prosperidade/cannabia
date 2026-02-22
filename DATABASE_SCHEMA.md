# DATABASE_SCHEMA.md

## Visão geral

Este documento descreve o estado **real** do banco `cannabia` a partir de:

1. dump SQL mais recente (`cannabia_banco_de_dados.sql`);
2. DDL de runtime em repositórios (`CREATE TABLE IF NOT EXISTS`);
3. migração versionada atual (`migrations/001_initial_schema.sql`);
4. queries em `src/repositories/` e uso em rotas/serviços/tenancy.

---

## 1) Inventário completo de tabelas (dump atual)

## 1.1 `clinics` (global)
**Propósito no sistema:** cadastro de clínicas/tenants. É a tabela raiz de tenancy.

| Coluna | Tipo | NULL | Default |
|---|---|---|---|
| id | int(11) | NÃO | auto_increment |
| name | varchar(255) | NÃO | - |
| slug | varchar(64) | NÃO | - |
| is_active | tinyint(1) | NÃO | 1 |
| created_at | timestamp | NÃO | CURRENT_TIMESTAMP |
| updated_at | timestamp | NÃO | CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP |

**PK:** `id`  
**Índices:** `PRIMARY(id)`, `UNIQUE(slug)`  
**FKs recebidas:** várias tabelas referenciam `clinics(id)`.

## 1.2 `users` (global)
**Propósito no sistema:** autenticação (login Flask-Login) e autorização por papel em `users.role`.

| Coluna | Tipo | NULL | Default |
|---|---|---|---|
| id | int(11) | NÃO | auto_increment |
| username | varchar(50) | NÃO | - |
| password_hash | varchar(255) | NÃO | - |
| role | varchar(20) | NÃO | 'Medico' |
| is_active | tinyint(1) | SIM | 1 |
| created_at | timestamp | NÃO | CURRENT_TIMESTAMP |

**PK:** `id`  
**Índices:** `PRIMARY(id)`, `UNIQUE(username)`  
**FKs:** nenhuma.

## 1.3 `user_clinics` (associação usuário-clínica)
**Propósito no sistema:** vínculo de usuários a clínicas, papel por clínica e clínica padrão.

| Coluna | Tipo | NULL | Default |
|---|---|---|---|
| user_id | int(11) | NÃO | - |
| clinic_id | int(11) | NÃO | - |
| role | enum('clinic_admin','doctor','staff','auditor') | NÃO | - |
| is_default | tinyint(1) | NÃO | 0 |
| created_at | timestamp | NÃO | CURRENT_TIMESTAMP |

**PK composta:** `(user_id, clinic_id)`  
**Índices:** `idx_uc_clinic(clinic_id)`, `idx_uc_user(user_id)`  
**FKs:** `user_id -> users(id) ON DELETE CASCADE`, `clinic_id -> clinics(id) ON DELETE CASCADE`.

## 1.4 `patients` (tenantada)
**Propósito no sistema:** entidade paciente usada pelo fluxo de IA e dados clínicos.

| Coluna | Tipo | NULL | Default |
|---|---|---|---|
| id | int(11) | NÃO | auto_increment |
| clinic_id | int(11) | NÃO | 1 |
| name | varchar(100) | NÃO | - |
| email | varchar(100) | SIM | NULL |
| phone | varchar(20) | SIM | NULL |
| created_at | timestamp | NÃO | CURRENT_TIMESTAMP |

**PK:** `id`  
**Índices:** `idx_patients_clinic(clinic_id)`  
**FKs:** `clinic_id -> clinics(id)`.

## 1.5 `appointments` (tenantada)
**Propósito no sistema:** agenda de atendimentos.

| Coluna | Tipo | NULL | Default |
|---|---|---|---|
| id | int(11) | NÃO | auto_increment |
| clinic_id | int(11) | NÃO | 1 |
| patient_id | int(11) | NÃO | - |
| appointment_date | datetime | NÃO | - |
| status | varchar(50) | SIM | NULL |
| created_at | timestamp | NÃO | CURRENT_TIMESTAMP |

**PK:** `id`  
**Índices:** `patient_id`, `idx_appointments_clinic(clinic_id)`  
**FKs:** `patient_id -> patients(id)`, `clinic_id -> clinics(id)`.

## 1.6 `incoming_messages` (tenantada)
**Propósito no sistema:** armazenamento de mensagens recebidas via webhook/WhatsApp.

| Coluna | Tipo | NULL | Default |
|---|---|---|---|
| id | int(11) | NÃO | auto_increment |
| clinic_id | int(11) | NÃO | 1 |
| sender | varchar(50) | SIM | NULL |
| contact_name | varchar(100) | SIM | NULL |
| message_text | text | SIM | NULL |
| timestamp | varchar(50) | SIM | NULL |

**PK:** `id`  
**Índices:** `idx_incoming_clinic(clinic_id)`  
**FKs:** `clinic_id -> clinics(id)`.

## 1.7 `message_status_updates` (tenantada)
**Propósito no sistema:** status de mensagens/template do WhatsApp.

| Coluna | Tipo | NULL | Default |
|---|---|---|---|
| id | int(11) | NÃO | auto_increment |
| clinic_id | int(11) | NÃO | 1 |
| message_id | varchar(100) | NÃO | - |
| status | varchar(50) | NÃO | - |
| timestamp | varchar(50) | SIM | NULL |
| created_at | timestamp | NÃO | CURRENT_TIMESTAMP |

**PK:** `id`  
**Índices:** `idx_msu_clinic(clinic_id)`, `idx_msu_message_id(message_id)`  
**FKs:** `clinic_id -> clinics(id)`.

## 1.8 `medical_history` (tenantada)
**Propósito no sistema:** histórico médico textual do paciente.

| Coluna | Tipo | NULL | Default |
|---|---|---|---|
| id | int(11) | NÃO | auto_increment |
| clinic_id | int(11) | NÃO | 1 |
| patient_id | int(11) | NÃO | - |
| history | text | SIM | NULL |
| created_at | timestamp | NÃO | CURRENT_TIMESTAMP |

**PK:** `id`  
**Índices:** `patient_id`, `idx_mh_clinic(clinic_id)`  
**FKs:** `patient_id -> patients(id)`, `clinic_id -> clinics(id)`.

## 1.9 `monitoring` (tenantada)
**Propósito no sistema:** acompanhamento/monitoramento clínico do paciente.

| Coluna | Tipo | NULL | Default |
|---|---|---|---|
| id | int(11) | NÃO | auto_increment |
| clinic_id | int(11) | NÃO | 1 |
| patient_id | int(11) | NÃO | - |
| status | varchar(50) | SIM | NULL |
| notes | text | SIM | NULL |
| created_at | timestamp | NÃO | CURRENT_TIMESTAMP |

**PK:** `id`  
**Índices:** `patient_id`, `idx_monitoring_clinic(clinic_id)`  
**FKs:** `patient_id -> patients(id)`, `clinic_id -> clinics(id)`.

## 1.10 `treatment_plans` (tenantada)
**Propósito no sistema:** plano terapêutico por paciente.

| Coluna | Tipo | NULL | Default |
|---|---|---|---|
| id | int(11) | NÃO | auto_increment |
| clinic_id | int(11) | NÃO | 1 |
| patient_id | int(11) | NÃO | - |
| plan_description | text | SIM | NULL |
| created_at | timestamp | NÃO | CURRENT_TIMESTAMP |

**PK:** `id`  
**Índices:** `patient_id`, `idx_tp_clinic(clinic_id)`  
**FKs:** `patient_id -> patients(id)`, `clinic_id -> clinics(id)`.

## 1.11 `alerts` (tenantada)
**Propósito no sistema:** alertas clínicos por paciente.

| Coluna | Tipo | NULL | Default |
|---|---|---|---|
| id | int(11) | NÃO | auto_increment |
| clinic_id | int(11) | NÃO | 1 |
| patient_id | int(11) | SIM | NULL |
| message | text | SIM | NULL |
| alert_time | timestamp | NÃO | CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP |
| created_at | timestamp | NÃO | CURRENT_TIMESTAMP |

**PK:** `id`  
**Índices:** `patient_id`, `idx_alerts_clinic(clinic_id)`  
**FKs:** `patient_id -> patients(id)`, `clinic_id -> clinics(id)`.

## 1.12 `ai_audit_logs` (tenantada)
**Propósito no sistema:** trilha de auditoria de chamadas de IA com custo, latência e status.

| Coluna | Tipo | NULL | Default |
|---|---|---|---|
| id | int(11) | NÃO | auto_increment |
| patient_id | int(11) | NÃO | - |
| clinic_id | int(11) | NÃO | 1 |
| request_id | varchar(36) | NÃO | - |
| user_id | varchar(50) | SIM | NULL |
| endpoint | varchar(100) | NÃO | - |
| input_payload | json | NÃO | - |
| output_payload | json | SIM | NULL |
| status | varchar(20) | NÃO | - |
| error_message | text | SIM | NULL |
| model | varchar(50) | NÃO | - |
| prompt_version | varchar(50) | NÃO | - |
| prompt_hash | varchar(64) | NÃO | - |
| input_tokens | int(11) | SIM | NULL |
| output_tokens | int(11) | SIM | NULL |
| total_tokens | int(11) | SIM | NULL |
| clinical_time_ms | int(11) | SIM | NULL |
| treatment_time_ms | int(11) | SIM | NULL |
| report_time_ms | int(11) | SIM | NULL |
| total_time_ms | int(11) | SIM | NULL |
| created_at | timestamp | NÃO | CURRENT_TIMESTAMP |
| estimated_cost_usd | decimal(10,6) | SIM | NULL |

**PK:** `id`  
**Índices:** `fk_ai_patient(patient_id)`, `idx_ai_request_id(request_id)`, `idx_ai_created_at(created_at)`, `idx_ai_status(status)`, `idx_ai_clinic_created(clinic_id, created_at)`  
**FKs:** `patient_id -> patients(id) ON DELETE CASCADE`, `clinic_id -> clinics(id)`.

## 1.13 `ai_prompt_versions` (global)
**Propósito no sistema:** versionamento de prompts (não há uso ativo nas queries de runtime atuais).

| Coluna | Tipo | NULL | Default |
|---|---|---|---|
| id | int(11) | NÃO | auto_increment |
| name | varchar(50) | NÃO | - |
| version | varchar(50) | NÃO | - |
| prompt_text | text | NÃO | - |
| hash | varchar(64) | NÃO | - |
| active | tinyint(1) | SIM | 1 |
| created_at | timestamp | NÃO | CURRENT_TIMESTAMP |

**PK:** `id`  
**Índices:** `PRIMARY(id)`  
**FKs:** nenhuma.

## 1.14 `scientific_references` (global)
**Propósito no sistema:** referências científicas (não há uso ativo nas queries de runtime atuais).

| Coluna | Tipo | NULL | Default |
|---|---|---|---|
| id | int(11) | NÃO | auto_increment |
| reference_title | varchar(255) | SIM | NULL |
| reference_url | varchar(255) | SIM | NULL |
| created_at | timestamp | NÃO | CURRENT_TIMESTAMP |

**PK:** `id`  
**Índices:** `PRIMARY(id)`  
**FKs:** nenhuma.

---

## 2) Multi-tenancy (`clinic_id`) e segurança de isolamento

## 2.1 Estratégia atual no código
- `src/tenancy.py` injeta `g.clinic_id` por request autenticada a partir de `session[active_clinic_id]` + `user_clinics`.
- Apenas `ai_audit_repository.py` usa consistentemente `clinic_id` em `INSERT`/`SELECT`.
- Repositórios de mensagens, pacientes e agenda **não filtram** por `clinic_id`.

## 2.2 Tabelas tenantadas (devem sempre usar filtro)
`patients`, `appointments`, `incoming_messages`, `message_status_updates`, `medical_history`, `monitoring`, `treatment_plans`, `alerts`, `ai_audit_logs`.

Padrão obrigatório de query:
```sql
... WHERE clinic_id = %s
```

## 2.3 Tabelas globais
`clinics`, `users`, `user_clinics`, `ai_prompt_versions`, `scientific_references`.

## 2.4 Riscos de vazamento hoje
1. `message_repository.list_messages()` lista tudo sem `clinic_id`; idem agregações.
2. `patient_repository.get_patient_by_name()` busca por nome sem `clinic_id`.
3. `appointment_repository.list_appointments()` lista tudo sem `clinic_id`.
4. Inserts em mensagens/appointments/patients não recebem `clinic_id` explicitamente (dependem de default `1`).

---

## 3) Divergências (drift) identificadas

## 3.1 Dump vs DDL de runtime (`CREATE TABLE IF NOT EXISTS`)

### `appointments`
- **Dump:** `patient_id`, `clinic_id` com FK.
- **Runtime/migration:** `patient_name`, sem `clinic_id`, sem FK.
- Impacto: código de agenda escreve em estrutura incompatível com o dump.

### `incoming_messages`
- **Dump:** possui `clinic_id` (NOT NULL + FK), sem `created_at`.
- **Runtime/migration:** sem `clinic_id`; migration adiciona `created_at`.

### `message_status_updates`
- **Dump:** `clinic_id` obrigatório, `message_id/status` NOT NULL.
- **Runtime/migration:** sem `clinic_id`; em migration `message_id/status` permitem NULL por omissão de `NOT NULL`.

### `patients`
- **Dump:** inclui `clinic_id` NOT NULL + FK.
- **Migration:** não inclui `clinic_id`.

## 3.2 Dump vs queries do código
- `appointment_repository.create_appointment` faz `INSERT INTO appointments (patient_name, ...)`; coluna `patient_name` **não existe** no dump.
- `appointment_repository.list_appointments` faz `SELECT *` sem filtro tenant.
- `patient_repository` cria/busca paciente sem `clinic_id`.
- `message_repository` faz inserts/selects/agregações sem `clinic_id`.
- `ai_audit_repository` está alinhado com dump para campos e filtro tenant.

## 3.3 Tabela/coluna usada no código e ausente no dump
- `appointments.patient_name` (usada no código, ausente no dump).
- `incoming_messages.created_at` (esperada pela migration, ausente no dump).

## 3.4 Tabela/coluna no dump sem uso no código atual
- Tabelas sem query ativa: `ai_prompt_versions`, `scientific_references`, `alerts`, `medical_history`, `monitoring`, `treatment_plans`.
- Colunas sem uso explícito nas queries atuais: `users.created_at`, `clinics.updated_at` e várias colunas clínicas/auxiliares fora de IA/mensageria.

---

## 4) Queries por Repositório

## 4.1 `src/repositories/ai_audit_repository.py`
- `INSERT INTO ai_audit_logs (...) VALUES (...)`
  - Parâmetros: `patient_id`, `clinic_id(g.clinic_id)`, `request_id`, `user_id`, `endpoint`, payloads, status, métricas.
- `SELECT COUNT(*), SUM(total_tokens), SUM(estimated_cost_usd) FROM ai_audit_logs WHERE status='success' AND clinic_id=%s`
  - Parâmetro: `clinic_id`.
- `SELECT id, patient_id, status, total_tokens, estimated_cost_usd, created_at FROM ai_audit_logs WHERE clinic_id=%s ORDER BY id DESC LIMIT %s`
  - Parâmetros: `clinic_id`, `limit`.

## 4.2 `src/repositories/message_repository.py`
- DDL runtime: `CREATE TABLE IF NOT EXISTS incoming_messages (...)`.
- DDL runtime: `CREATE TABLE IF NOT EXISTS message_status_updates (...)`.
- `INSERT INTO incoming_messages (sender, contact_name, message_text, timestamp) VALUES (%s, %s, %s, %s)`.
- `INSERT INTO message_status_updates (message_id, status, timestamp) VALUES (%s, %s, %s)`.
- `SELECT * FROM incoming_messages WHERE sender=%s ORDER BY id DESC` (quando filtro).
- `SELECT * FROM incoming_messages ORDER BY id DESC`.
- `SELECT contact_name, COUNT(*) AS message_count FROM incoming_messages GROUP BY contact_name`.
- Query de agregação diária em `incoming_messages` convertendo `timestamp` para data.

> Observação: todas as queries acima deveriam receber `clinic_id`.

## 4.3 `src/repositories/patient_repository.py`
- `SELECT id, name FROM patients WHERE name=%s LIMIT 1`.
- `INSERT INTO patients (name) VALUES (%s)`.

> Observação: falta `clinic_id` em SELECT/INSERT.

## 4.4 `src/repositories/appointment_repository.py`
- DDL runtime: `CREATE TABLE IF NOT EXISTS appointments (patient_name, ...)`.
- `INSERT INTO appointments (patient_name, appointment_date, status) VALUES (%s, %s, %s)`.
- `SELECT * FROM appointments ORDER BY appointment_date DESC`.

> Observação: incompatível com dump (espera `patient_id` + `clinic_id`).

## 4.5 `src/repositories/tenancy_repository.py`
- `SELECT clinic_id, role, is_default FROM user_clinics WHERE user_id=%s AND clinic_id=%s LIMIT 1`.
- `SELECT clinic_id FROM user_clinics WHERE user_id=%s AND is_default=1 LIMIT 1`.
- `SELECT clinic_id FROM user_clinics WHERE user_id=%s ORDER BY created_at ASC LIMIT 1`.

## 4.6 `src/repositories/user_repository.py`
- `INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)`.
- `SELECT * FROM users WHERE username=%s AND is_active=1`.
- `SELECT * FROM users WHERE id=%s AND is_active=1`.

---

## 5) Checklist de Convergência (eliminar drift)

1. **Parar DDL em runtime**: remover `ensure_*_table()` de repositórios e centralizar DDL em migrações versionadas.
2. **Criar migração V2** alinhando estrutura canônica:
   - `appointments` com `patient_id`, `clinic_id`, FKs, índices.
   - `incoming_messages/message_status_updates/patients` com `clinic_id` obrigatório.
3. **Refatorar repositórios para tenancy obrigatória**:
   - assinatura de métodos com `clinic_id` (ou leitura explícita de `g.clinic_id` no service layer);
   - todos os `SELECT/UPDATE/DELETE` com `WHERE clinic_id=%s`.
4. **Corrigir fluxo de agenda**:
   - trocar `patient_name` por resolução `patient_id` tenant-aware.
5. **Corrigir fluxo de pacientes**:
   - `get_patient_by_name(name, clinic_id)`;
   - `create_patient(name, clinic_id)`.
6. **Adicionar testes de regressão multi-tenant** para mensagens, pacientes, agenda e agregações.
7. **Definir fonte única da verdade**:
   - dump deve ser resultado de migrações aplicadas (não o contrário);
   - atualizar `migrations/001_initial_schema.sql` ou substituir por baseline novo consistente.
8. **Auditar coerência de papéis** (`users.role` vs `user_clinics.role`) e mapear conversão em código para evitar regras conflitantes.

---

## 6) Test Plan Multi-tenant

## 6.1 Preparação
- Criar `clinic A` e `clinic B`.
- Criar 1 usuário com acesso às duas clínicas em `user_clinics`.
- Inserir dados espelhados por tabela tenantada (`patients`, `appointments`, `incoming_messages`, `message_status_updates`, `ai_audit_logs`).

## 6.2 Casos SELECT
1. Listagem de mensagens em contexto clinic A não retorna linhas da clinic B.
2. Agregação por contato e por dia em clinic A considera apenas clinic A.
3. Listagem de appointments em clinic A não mostra clinic B.
4. Busca de paciente por nome retorna paciente da clínica ativa.
5. Dashboard de auditoria IA soma apenas `clinic_id` ativo.

## 6.3 Casos UPDATE/DELETE
1. UPDATE de `appointments.status` com `WHERE id=%s AND clinic_id=%s` não afeta outra clínica.
2. DELETE de mensagem por `id` sem `clinic_id` deve falhar em teste de segurança (query proibida).
3. Atualizações em lote (ex.: fechamento do dia) devem incluir `clinic_id` no predicado.

## 6.4 Casos de agregação
1. `COUNT(*)`, `SUM()`, `AVG()` em mensagens e auditoria com filtro tenant.
2. Validar que remover filtro tenant muda resultado (teste de controle negativo).

## 6.5 Casos de consistência relacional
1. Inserir `appointments` com `patient_id` de outra clínica deve ser bloqueado por regra de aplicação e/ou constraint adicional.
2. Verificar orfandade após deleção de paciente (`ai_audit_logs` tem `ON DELETE CASCADE`; demais tabelas devem ter comportamento definido).

## 6.6 Automação recomendada
- Testes de integração que varrem todas as funções de repositório e garantem presença de `clinic_id` nos filtros.
- Lint SQL simples no CI para bloquear queries sem predicado tenant em tabelas tenantadas.
