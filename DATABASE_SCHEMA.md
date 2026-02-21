# DATABASE_SCHEMA.md

## 1) Introduction

This document explains the current MySQL schema used by Cannab'IA and how to query it safely.

Important context:

- There are two schema sources in the repository:
  1. `migrations/001_initial_schema.sql` (minimal bootstrap)
  2. `cannabia banco de dados.sql` (fuller historical dump)
- Runtime code also creates some tables with `CREATE TABLE IF NOT EXISTS` from repository methods.

Because of this, developers must verify actual production schema before making migrations.

---

## 2) Core Tables by Functional Area

## 2.1 Identity and Access

### `users` (referenced by code, not defined in current migration file)

Expected columns used by application code:

- `id` (PK)
- `username`
- `password_hash`
- `role`
- `is_active`

Used by:

- login (`get_user_by_username`)
- session reload (`get_user_by_id`)
- admin user creation script (`create_user`)

## 2.2 Messaging and Realtime

### `incoming_messages`

Columns (from migration/runtime definitions):

- `id` INT PK auto increment
- `sender` VARCHAR(50)
- `contact_name` VARCHAR(100)
- `message_text` TEXT
- `timestamp` VARCHAR(50)
- (sometimes) `created_at` TIMESTAMP in some schema variants

Purpose:

- Stores inbound WhatsApp message events.

### `message_status_updates`

Columns:

- `id` INT PK auto increment
- `message_id` VARCHAR(100)
- `status` VARCHAR(50)
- `timestamp` VARCHAR(50)
- (sometimes) `created_at` TIMESTAMP in migration variant

Purpose:

- Tracks outbound template status updates.

## 2.3 Patient and Clinical Data

### `patients`

Columns:

- `id` INT PK auto increment
- `name` VARCHAR(100)
- `email` VARCHAR(100) [variant dependent]
- `phone` VARCHAR(20) [variant dependent]
- `created_at` TIMESTAMP

Purpose:

- Root patient entity.

### `appointments`

Two variants exist:

1. Minimal/runtime variant uses `patient_name` text directly.
2. Full dump variant uses `patient_id` FK.

Columns observed across variants:

- `id` PK
- either `patient_name` or `patient_id`
- `appointment_date` DATETIME
- `status` VARCHAR(50)
- `created_at` TIMESTAMP

### Other clinical tables (from full SQL dump)

- `medical_history` (`patient_id` FK)
- `monitoring` (`patient_id` FK)
- `treatment_plans` (`patient_id` FK)
- `alerts` (`patient_id` FK)
- `scientific_references`

These may represent historical/extended schema not fully reflected in active repository code.

## 2.4 AI Audit and Metrics

### `ai_audit_logs` (referenced by code)

Expected columns inferred from repository inserts/queries:

- `id` (PK)
- `patient_id`
- `request_id`
- `user_id`
- `endpoint`
- `input_payload` (JSON serialized text)
- `output_payload` (JSON serialized text)
- `status`
- `error_message`
- `model`
- `prompt_version`
- `prompt_hash`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `clinical_time_ms`
- `treatment_time_ms`
- `report_time_ms`
- `total_time_ms`
- `estimated_cost_usd`
- `created_at`

Purpose:

- Complete trace of AI requests, success/failure reasons, token usage, latency and estimated cost.

---

## 3) Relationship Diagram (Conceptual)

```text
users
  | (user_id in ai_audit_logs)
  v
ai_audit_logs ---> patients
                    ^
                    |
       appointments / medical_history / monitoring / treatment_plans / alerts
```

And messaging domain:

```text
incoming_messages ----(message_id logical reference)---> message_status_updates
```

---

## 4) Foreign Keys and Indexes

From full SQL dump:

- `alerts.patient_id -> patients.id`
- `appointments.patient_id -> patients.id` (in FK variant)
- `medical_history.patient_id -> patients.id`
- `monitoring.patient_id -> patients.id`
- `treatment_plans.patient_id -> patients.id`

Indexes explicitly shown:

- PK indexes on all major tables
- secondary index on each `patient_id` FK column

Operational recommendation for high-volume systems:

- Ensure indexes exist on frequently filtered columns:
  - `incoming_messages.sender`
  - `appointments.appointment_date`
  - `ai_audit_logs.created_at`
  - `ai_audit_logs.status`
  - future `clinic_id` columns

---

## 5) Tenant Isolation and `clinic_id` Strategy

Current code does not consistently include `clinic_id`. For safe multi-clinic operations, every tenant-owned table should include:

- `clinic_id` (NOT NULL)
- index on `clinic_id`
- composite indexes by query pattern (e.g., `(clinic_id, created_at)`)

Example secure query pattern:

```sql
SELECT id, sender, message_text, timestamp
FROM incoming_messages
WHERE clinic_id = %s
ORDER BY id DESC
LIMIT 100;
```

Insecure pattern (cross-tenant leak risk):

```sql
SELECT id, sender, message_text, timestamp
FROM incoming_messages
ORDER BY id DESC
LIMIT 100;
```

---

## 6) Example Queries (Correct Tenant Filtering)

### 6.1 Get appointments for one clinic only

```sql
SELECT a.id, a.appointment_date, a.status, p.name AS patient_name
FROM appointments a
JOIN patients p ON p.id = a.patient_id
WHERE a.clinic_id = %s
  AND p.clinic_id = %s
ORDER BY a.appointment_date DESC;
```

### 6.2 AI cost summary for one clinic

```sql
SELECT
  COUNT(*) AS total_requests,
  COALESCE(SUM(total_tokens), 0) AS total_tokens,
  COALESCE(SUM(estimated_cost_usd), 0) AS total_cost_usd
FROM ai_audit_logs
WHERE clinic_id = %s
  AND status = 'success';
```

### 6.3 Detect suspicious cross-clinic references

```sql
SELECT a.id, a.patient_id, a.clinic_id, p.clinic_id AS patient_clinic
FROM appointments a
JOIN patients p ON p.id = a.patient_id
WHERE a.clinic_id <> p.clinic_id;
```

If this query returns rows, tenant integrity is broken.

---

## 7) Cross-Tenant Leakage Test Plan (Database Level)

Use two clinics in test data (`clinic_id=1` and `clinic_id=2`):

1. Insert records for both clinics.
2. Execute every repository SELECT as clinic 1 user context.
3. Assert no row from clinic 2 is returned.
4. Repeat for UPDATE and DELETE paths.
5. Validate aggregate queries (`COUNT`, `SUM`, grouped reports).

Common leakage point:

- developers add tenant filter in list query but forget aggregate query.

---

## 8) Schema Governance Rules

1. Never rely only on app-level filtering; store tenant identity in DB rows.
2. Use foreign keys with clinic-aware consistency where possible.
3. Add migration + rollback scripts for all schema changes.
4. Keep migration files as source of truth; avoid schema drift from runtime DDL.
5. Document each new table in this file before production rollout.

---

## 9) Glossary

- **PK (Primary Key)**: unique row identifier.
- **FK (Foreign Key)**: DB rule linking child rows to parent rows.
- **Index**: data structure that speeds up query filtering/sorting.
- **Schema drift**: DB structure differs from migration history.
- **Tenant filter**: mandatory `WHERE clinic_id = ...` constraint.
