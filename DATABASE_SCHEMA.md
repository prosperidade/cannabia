# DATABASE_SCHEMA.md

## 1) Scope

This schema document is based only on the current repository state:

- migration file: `migrations/001_initial_schema.sql`
- active SQL usage in `src/repositories/*`

No external assumptions are used.

---

## 2) Migration-Defined Tables

The current migration defines four tables.

## 2.1 `patients`

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| id | INT AUTO_INCREMENT | NO | - | Primary key |
| name | VARCHAR(100) | NO | - | Patient name |
| email | VARCHAR(100) | YES | NULL | Optional email |
| phone | VARCHAR(20) | YES | NULL | Optional phone |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | Record creation time |

## 2.2 `incoming_messages`

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| id | INT AUTO_INCREMENT | NO | - | Primary key |
| sender | VARCHAR(50) | YES | NULL | Sender identifier |
| contact_name | VARCHAR(100) | YES | NULL | Contact display name |
| message_text | TEXT | YES | NULL | Message body |
| timestamp | VARCHAR(50) | YES | NULL | Provider timestamp string |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | Ingestion timestamp |

## 2.3 `message_status_updates`

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| id | INT AUTO_INCREMENT | NO | - | Primary key |
| message_id | VARCHAR(100) | YES | NULL | Provider message reference |
| status | VARCHAR(50) | YES | NULL | Delivery status |
| timestamp | VARCHAR(50) | YES | NULL | Provider timestamp |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | Ingestion timestamp |

## 2.4 `appointments`

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| id | INT AUTO_INCREMENT | NO | - | Primary key |
| patient_name | VARCHAR(100) | YES | NULL | Patient name text |
| appointment_date | DATETIME | NO | - | Appointment date-time |
| status | VARCHAR(50) | YES | NULL | Appointment status |
| created_at | TIMESTAMP | YES | CURRENT_TIMESTAMP | Record creation time |

---

## 3) Tables Required by Current Application Code

In addition to migration-defined tables, current repositories reference these tables:

1. `users`
2. `ai_audit_logs`

## 3.1 `users`

Used by authentication flows (`user_repository`):

Expected columns from current queries:

- `id`
- `username`
- `password_hash`
- `role`
- `is_active`

Query patterns:

- user lookup by username + active flag
- user lookup by id + active flag
- user creation with username/password_hash/role

## 3.2 `ai_audit_logs`

Used by AI pipeline auditing (`ai_audit_repository`):

Expected write fields from current insert function:

- `patient_id`, `request_id`, `user_id`, `endpoint`
- `input_payload`, `output_payload`
- `status`, `error_message`
- `model`, `prompt_version`, `prompt_hash`
- `input_tokens`, `output_tokens`, `total_tokens`
- `clinical_time_ms`, `treatment_time_ms`, `report_time_ms`, `total_time_ms`
- `estimated_cost_usd`

Expected read fields in dashboards:

- `id`, `patient_id`, `status`, `total_tokens`, `estimated_cost_usd`, `created_at`

---

## 4) Relationship Diagram (Current Logical Model)

```text
users
  |
  | user_id (logical reference)
  v
ai_audit_logs
  ^
  | patient_id (logical reference)
  |
patients

incoming_messages --(message lifecycle relation)--> message_status_updates

appointments (stores patient_name text; no FK in current migration)
```

Current migration does not define foreign keys across these tables.

---

## 5) Keys and Indexes

From current migration:

- each migration-defined table has primary key on `id`.

No secondary indexes are declared in migration for common filters like:

- message sender,
- appointment date,
- status/time dimensions.

---

## 6) Tenant / `clinic_id` Schema Status

Based on current migration and repository SQL:

- no `clinic_id` columns,
- no tenant foreign keys,
- no tenant-specific indexes.

Therefore, there is currently no DB-level tenant partitioning in schema.

---

## 7) Repository Query Security Pattern

### Secure pattern in current code

Current repository queries use parameter placeholders.

```sql
SELECT * FROM users WHERE username = %s AND is_active = 1
```

### Insecure anti-pattern (do not use)

```sql
SELECT * FROM users WHERE username = '" + username + "' AND is_active = 1
```

This anti-pattern enables SQL injection.

---

## 8) Data Flow by Table

### Messaging flow

1. webhook message event arrives,
2. row inserted into `incoming_messages`,
3. status updates inserted into `message_status_updates`.

### Scheduling flow

1. form POST validated,
2. appointment row inserted into `appointments`.

### AI flow

1. AI request processed,
2. patient resolved/created in `patients`,
3. audit row inserted in `ai_audit_logs`.

### Auth flow

1. login checks `users` table,
2. user id reloaded from `users` during session lifecycle.

---

## 9) Secure vs Insecure Tenant Query Examples (Conceptual)

Current code is single-tenant; examples below are conceptual for future tenantized schema.

### Secure tenantized query

```sql
SELECT id, message_text
FROM incoming_messages
WHERE clinic_id = %s
ORDER BY id DESC;
```

### Insecure tenantized query

```sql
SELECT id, message_text
FROM incoming_messages
ORDER BY id DESC;
```

In multi-clinic systems, missing `clinic_id` filter risks cross-tenant leakage.

---

## 10) Glossary

- **Primary Key (PK)**: unique row identifier.
- **Foreign Key (FK)**: relational constraint to another table.
- **Parameterized SQL**: query placeholders with separate values.
- **Denormalized field**: text value stored instead of FK relation.
- **Schema drift**: mismatch between expected and actual DB structure.
