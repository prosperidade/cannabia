# DATABASE_SCHEMA.md

## 1) Scope and Source of Truth

This schema documentation is based strictly on:

- `migrations/001_initial_schema.sql`
- repository SQL currently executed in `src/repositories/*`

This means the document reflects the schema that the current code expects and uses.

---

## 2) Tables Defined in Current Migration

Current migration defines these tables:

1. `patients`
2. `incoming_messages`
3. `message_status_updates`
4. `appointments`

### 2.1 `patients`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | INT AUTO_INCREMENT | NO | - | Primary key |
| name | VARCHAR(100) | NO | - | Patient name |
| email | VARCHAR(100) | YES | NULL | Optional |
| phone | VARCHAR(20) | YES | NULL | Optional |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | Creation timestamp |

### 2.2 `incoming_messages`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | INT AUTO_INCREMENT | NO | - | Primary key |
| sender | VARCHAR(50) | YES | NULL | Sender phone/id |
| contact_name | VARCHAR(100) | YES | NULL | Display name |
| message_text | TEXT | YES | NULL | Message body |
| timestamp | VARCHAR(50) | YES | NULL | Provider timestamp string |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | Ingestion time |

### 2.3 `message_status_updates`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | INT AUTO_INCREMENT | NO | - | Primary key |
| message_id | VARCHAR(100) | YES | NULL | Provider message reference |
| status | VARCHAR(50) | YES | NULL | Delivery/template status |
| timestamp | VARCHAR(50) | YES | NULL | Provider timestamp |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | Ingestion time |

### 2.4 `appointments`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | INT AUTO_INCREMENT | NO | - | Primary key |
| patient_name | VARCHAR(100) | YES | NULL | Denormalized patient name |
| appointment_date | DATETIME | NO | - | Appointment datetime |
| status | VARCHAR(50) | YES | NULL | Status text |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | Creation timestamp |

---

## 3) Tables Required by Current Application Code

Beyond migration-defined tables, code references two additional tables:

1. `users`
2. `ai_audit_logs`

These are required for authentication and AI audit dashboards.

## 3.1 `users` (used by `user_repository`)

Code expects at least:

- `id`
- `username`
- `password_hash`
- `role`
- `is_active`

SQL usage patterns:

- `SELECT * FROM users WHERE username = %s AND is_active = 1`
- `SELECT * FROM users WHERE id = %s AND is_active = 1`
- insert with `(username, password_hash, role)`

## 3.2 `ai_audit_logs` (used by `ai_audit_repository`)

Insert expects fields:

- identity/context: `patient_id`, `request_id`, `user_id`, `endpoint`
- payloads: `input_payload`, `output_payload`
- result metadata: `status`, `error_message`
- model metadata: `model`, `prompt_version`, `prompt_hash`
- usage/timing: `input_tokens`, `output_tokens`, `total_tokens`, `clinical_time_ms`, `treatment_time_ms`, `report_time_ms`, `total_time_ms`
- finance: `estimated_cost_usd`

Dashboard queries also expect `id` and `created_at`.

---

## 4) Relationship View

Current migration-level relationships are denormalized/simple (no FKs declared).

Conceptual relationships from code usage:

```text
patients
  ^
  | (patient_id in AI logs, logical relationship)
ai_audit_logs

incoming_messages ----logical/event relation---- message_status_updates

users ----(user_id in ai_audit_logs)---- ai_audit_logs
```

`appointments` currently stores `patient_name` text instead of a patient FK in the migration schema.

---

## 5) Indexes and Keys

Migration explicitly creates:

- Primary key on `id` for all migration-defined tables.

No extra indexes are defined in migration for:

- sender-based filtering,
- status filtering,
- date filtering,
- AI audit aggregations.

If large data volumes are expected, index strategy should be documented alongside future migrations.

---

## 6) Query Patterns in Repositories

### 6.1 Secure pattern currently used

All repository SQL uses parameter placeholders `%s` with tuple parameters.

Example:

```sql
SELECT * FROM users WHERE username = %s AND is_active = 1
```

This protects against SQL injection by avoiding string concatenation.

### 6.2 Insecure anti-pattern (not used)

```sql
SELECT * FROM users WHERE username = '" + username + "'
```

Never use this concatenation style.

---

## 7) Tenancy/clinic_id Schema Status

Current schema and repositories do not include `clinic_id` columns, tenant foreign keys, or tenant filters.

Therefore, this codebase’s current data model is not tenant-partitioned by clinic inside SQL queries.

---

## 8) Data Flow by Table

### Messaging flow

1. Webhook receives message event.
2. `incoming_messages` row inserted.
3. Status update events insert into `message_status_updates`.

### Scheduling flow

1. Scheduling form posted.
2. Date string normalized.
3. `appointments` row inserted.

### AI flow

1. AI endpoint called.
2. Patient resolved via `patients` table.
3. Audit row inserted into `ai_audit_logs`.

---

## 9) Diagram: Operational Data Paths

```text
Webhook POST --> incoming_messages
Webhook status --> message_status_updates

Schedule POST --> appointments

AI POST --> patients (get/create) --> ai_audit_logs

Login --> users
```

---

## 10) Glossary

- **Denormalized column**: stores text directly instead of FK relation.
- **Primary key**: unique identifier per row.
- **Parameterized query**: SQL query with placeholders and separate values.
- **Schema drift**: when runtime database differs from migration definition.
- **Audit table**: table for traceability/observability rather than core business entity storage.
