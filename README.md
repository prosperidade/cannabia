# Cannab'IA — Production Flask Application

Cannab'IA is a Flask-based clinical operations platform that combines secure web access, WhatsApp event ingestion, realtime dashboards, scheduling workflows, and an AI clinical pipeline with audit logging.

This documentation is intentionally written for junior developers. It explains **what exists now in this repository** and **why each part behaves the way it does**.

---

## Table of Contents

1. [System Purpose](#system-purpose)
2. [Current Feature Set](#current-feature-set)
3. [Architecture Overview](#architecture-overview)
4. [Flask Request Lifecycle](#flask-request-lifecycle)
5. [Authentication, Sessions, and RBAC](#authentication-sessions-and-rbac)
6. [Multi-Clinic / Tenant Isolation Status](#multi-clinic--tenant-isolation-status)
7. [Database at a Glance](#database-at-a-glance)
8. [AI Pipeline at a Glance](#ai-pipeline-at-a-glance)
9. [Route Catalog](#route-catalog)
10. [Security Controls Implemented](#security-controls-implemented)
11. [How to Run Locally](#how-to-run-locally)
12. [Operational Checklist for Maintainers](#operational-checklist-for-maintainers)
13. [Document Map](#document-map)
14. [Glossary](#glossary)

---

## System Purpose

Cannab'IA supports day-to-day clinic operations through five core capabilities:

1. User authentication and role-protected UI access.
2. Message/event ingestion from WhatsApp webhook callbacks.
3. Realtime operational visibility with Socket.IO.
4. Appointment scheduling through form workflow.
5. AI-assisted structured clinical output generation with persistent audit logs.

---

## Current Feature Set

### 1) User Access and Sessions

- Login and logout flows exist in the main app.
- Session auth is managed by Flask-Login.
- Password verification uses bcrypt hashes from database records.
- CSRF checks protect login/logout form actions.

### 2) Realtime Messaging

- Webhook endpoint verifies provider challenge (`GET`) and receives events (`POST`).
- Message and status events are parsed and persisted in MySQL.
- Realtime clients receive redacted event payloads via Socket.IO.

### 3) Scheduling

- Form-driven scheduling endpoint validates required fields and datetime format.
- Appointments are persisted and listed in dashboard view.

### 4) AI Clinical Flow

- JSON request enters `/ai/test`.
- Input security validation and schema validation run before model calls.
- 3-stage AI pipeline returns structured JSON only.
- Audit logs store request context, status, tokens, and estimated cost.

### 5) Operational Dashboards

- Message dashboard with aggregate charts by contact/day.
- AI audit dashboard and AI metrics dashboard.

---

## Architecture Overview

```text
                           +---------------------------+
                           | External Providers        |
                           | WhatsApp / OpenAI / SMTP  |
                           +-------------+-------------+
                                         |
                                         v
+---------------------------+   +--------+-----------------------------+
| Browser (clinic operator) |<->| Flask app (routes + auth + context) |
| session cookie + CSRF     |   | before_request / after_request       |
+-------------+-------------+   +---------+----------------------------+
              |                             |
              |                             +------------------------------+
              v                                                            v
+-------------+--------------+                           +-----------------+----------------+
| Socket.IO realtime channel |                           | AI service + pipeline + validators |
+-------------+--------------+                           +-----------------+----------------+
              |                                                            |
              v                                                            v
      +-------+-------------------------------+                +-----------+----------------+
      | Repositories (SQL via mysql.connector) |<------------>| AI audit repository         |
      | users/messages/appointments/patients   |                | token usage + cost + status |
      +----------------------------------------+                +-----------------------------+
```

---

## Flask Request Lifecycle

Every request follows the same top-level sequence:

1. **Route match**: Flask maps URL to route handler.
2. **`before_request` executes**:
   - start timer,
   - create `g.request_id`,
   - store authenticated `g.user_id` when available.
3. **Decorator checks execute**:
   - `login_required` for authenticated routes,
   - `role_required` for role-gated routes,
   - route-specific CSRF/rate-limit checks.
4. **Business logic executes**:
   - route invokes services and repositories.
5. **`after_request` executes**:
   - elapsed time is computed,
   - request metadata is logged.
6. **Response returns** to client.

Why this matters: request IDs and user context create traceability from UI action to DB/audit events.

---

## Authentication, Sessions, and RBAC

### Authentication

- Flask-Login `LoginManager` loads users from `users` table.
- User loader fetches active users (`is_active = 1`).
- Login compares plain password with stored `password_hash` via bcrypt.

### Session handling

- Session is cookie-based.
- Cookie hardening flags include `HttpOnly` and `SameSite=Lax`.
- CSRF tokens are generated/validated in form flows.

### RBAC behavior

- `role_required(*allowed_roles)` enforces role checks.
- Roles in active use:
  - `Admin`
  - `Medico`
  - `Atendente`

---

## Multi-Clinic / Tenant Isolation Status

### Current codebase status (source-of-truth from repository tree)

- There is **no** `src/tenancy.py` file in current codebase.
- There is **no** `tenancy_repository` module in current codebase.
- There are **no** `clinic_id` columns in current migration SQL (`migrations/001_initial_schema.sql`).
- Repository SQL functions currently do **not** enforce `WHERE clinic_id = ...` filtering.

### Practical implication

Current implementation behaves as a **single-tenant application at data-access layer**.

This section is explicit to prevent accidental assumptions that tenant boundaries are enforced in SQL.

---

## Database at a Glance

Migration-defined tables:

- `patients`
- `incoming_messages`
- `message_status_updates`
- `appointments`

Code-required additional tables:

- `users`
- `ai_audit_logs`

Detailed schema, relationships, query patterns, and key/index notes are documented in `DATABASE_SCHEMA.md`.

---

## AI Pipeline at a Glance

```text
POST /ai/test
   -> CannabIAService
      -> validate_anamnesis_security
      -> Pydantic input validation
      -> CannabIAPipeline (3 stages)
         1) clinical_analysis
         2) treatment_plan
         3) scientific_report
      -> token aggregation
      -> estimated cost calculation
      -> ai_audit_logs persistence
   -> JSON response
```

AI audit logs persist both success and failure paths.

---

## Route Catalog

| Route | Methods | Purpose | Access |
|---|---|---|---|
| `/` | GET | main navigation page | authenticated |
| `/login` | GET, POST | login form and auth | public |
| `/logout` | POST | session termination | authenticated + CSRF |
| `/whoami` | GET | debug auth context | public |
| `/dashboard` | GET | message dashboard | Admin, Medico |
| `/ai-audit` | GET | AI audit dashboard | Admin, Medico |
| `/admin/ai-metrics` | GET | AI cost/token metrics | authenticated |
| `/historico/historico` | GET | message history | Admin, Medico, Atendente |
| `/scheduling/scheduling` | GET, POST | appointment workflow | Admin, Medico, Atendente |
| `/realtime/` | GET | realtime dashboard | Admin, Medico, Atendente |
| `/realtime/webhook` | GET, POST | provider webhook | public endpoint with checks |
| `/ai/test` | POST | AI processing endpoint | authenticated |

---

## Security Controls Implemented

1. **CSRF** for sensitive form POST flows.
2. **Rate limiting** (in-memory, per process) for login and webhook.
3. **Request size limit** for webhook payloads.
4. **RBAC** with route decorators.
5. **Session cookie hardening** options configured in app.
6. **Sensitive data redaction** helper functions.
7. **Socket.IO auth check** on connect event.

---

## How to Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.app
```

Set required environment variables for DB, app secret, webhook settings, and OpenAI API key.

---

## Operational Checklist for Maintainers

Before merging changes:

1. Verify route auth and role requirements.
2. Verify CSRF enforcement for browser mutations.
3. Verify SQL queries remain parameterized.
4. Verify logs and events are redacted where needed.
5. Verify AI flow still writes complete audit records.
6. Update architecture/schema/security docs in same PR.

---

## Document Map

- `SYSTEM_ARCHITECTURE.md` — architecture and request flow deep dive.
- `DATABASE_SCHEMA.md` — schema and data flow details.
- `AUTHORIZATION_AND_MULTI_TENANCY.md` — auth/RBAC/tenancy status.
- `AI_MODULE_DOCUMENTATION.md` — AI pipeline and auditing details.
- `DEPLOYMENT_AND_PRODUCTION_GUIDE.md` — production hardening and operations.

---

## Glossary

- **Application Factory**: function that constructs Flask app and wiring.
- **Blueprint**: grouped Flask routes.
- **RBAC**: Role-Based Access Control.
- **CSRF**: Cross-Site Request Forgery prevention mechanism.
- **Webhook**: HTTP callback endpoint from external systems.
- **Socket.IO**: realtime messaging layer for browser updates.
- **Audit Log**: persistent record of processing outcomes and metadata.
- **Token Usage**: LLM usage counters used for billing/monitoring.
