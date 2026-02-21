# Cannab'IA

Cannab'IA is a production-oriented Flask application for clinical operations, real-time patient messaging workflows, scheduling, and AI-assisted clinical output generation.

This README is written for junior developers and operations engineers who need to understand the system safely before making changes.

---

## Table of Contents

1. [Platform Overview](#platform-overview)
2. [Current Production Capabilities](#current-production-capabilities)
3. [Architecture at a Glance](#architecture-at-a-glance)
4. [Request Lifecycle (Step by Step)](#request-lifecycle-step-by-step)
5. [Security Model Summary](#security-model-summary)
6. [Authorization and Access](#authorization-and-access)
7. [Tenancy and Clinic Isolation Status](#tenancy-and-clinic-isolation-status)
8. [AI Module Summary](#ai-module-summary)
9. [Database Summary](#database-summary)
10. [Local Setup](#local-setup)
11. [Operational Routes](#operational-routes)
12. [How to Work Safely as a Junior Developer](#how-to-work-safely-as-a-junior-developer)
13. [Glossary](#glossary)

---

## Platform Overview

Cannab'IA integrates several workflows into one Flask application:

- User login/logout with session-based authentication.
- Role-protected dashboards for operators and clinicians.
- WhatsApp webhook ingestion and real-time UI updates via Socket.IO.
- Appointment scheduling workflow.
- AI endpoint for structured clinical processing.
- AI audit visibility (request count, token usage, estimated cost).

The codebase follows a layered style:

- `web/routes` for HTTP entrypoints,
- `services` for business orchestration,
- `repositories` for SQL persistence,
- `ai` for model workflow,
- `infra` for DB/security/logging utilities.

---

## Current Production Capabilities

### Authentication and Sessions

- Flask-Login is used for user session management.
- User data is loaded from MySQL through `user_repository`.
- Password verification uses bcrypt.
- Login and logout flows include CSRF checks.

### Role-Based Route Protection

Route-level checks use the `role_required` decorator in `src/infra/security.py`.

Current roles present in enforcement logic:

- `Admin`
- `Medico`
- `Atendente`

### Realtime Messaging

- `/realtime/webhook` accepts WhatsApp events.
- Incoming payload is validated for basic structure.
- Events are persisted and emitted to authenticated realtime dashboard users.

### Scheduling

- `/scheduling/scheduling` supports form-based appointment creation.
- Appointment date format is validated in the service layer.

### AI Workflow

- `/ai/test` receives JSON anamnesis payload.
- Input security and schema validation happen before model execution.
- AI outputs are stored with usage/cost metadata in audit logs.

---

## Architecture at a Glance

```text
                    +----------------------+
                    | WhatsApp Cloud API   |
                    +----------+-----------+
                               |
                               v
 +------------------+   +------+-------------------------------+
 | Web Browser User |<->| Flask App (app.py + blueprints)     |
 | (session cookie) |   | auth, routes, before/after request   |
 +---------+--------+   +-----------+---------------------------+
           |                        |
           |                        +-------------------------+
           v                                                  v
 +---------+----------------+                     +-----------+----------+
 | Socket.IO Realtime Layer |                     | AI Service/Pipeline  |
 +---------+----------------+                     +-----------+----------+
           |                                                  |
           v                                                  v
 +---------+-------------------------------+      +-----------+----------+
 | Repositories (MySQL SQL execution)      |<-----| AI audit repository  |
 | users/messages/appointments/patients    |      | tokens/cost/status   |
 +-----------------------------------------+      +----------------------+
```

---

## Request Lifecycle (Step by Step)

Every request to Flask follows this pattern:

1. **Request enters Flask router**.
2. **`before_request` executes**:
   - starts request timer,
   - assigns `g.request_id`,
   - stores authenticated user id in `g.user_id` if present.
3. **Decorator checks execute**:
   - `login_required` if configured,
   - `role_required` if configured,
   - route-specific CSRF/rate-limit checks.
4. **Route handler executes**, typically calling services and repositories.
5. **`after_request` executes**:
   - computes elapsed time,
   - logs request metadata.
6. **Response returned**.

This flow is critical for observability and audit traceability.

---

## Security Model Summary

Implemented controls in current code:

- CSRF token generation/validation utilities.
- Session cookie hardening (`HttpOnly`, `SameSite`; secure flag currently set for local-style behavior in app config).
- In-memory IP-based rate limiting for login and webhook routes.
- Payload size check for webhook requests.
- Basic payload structure validation for webhook events.
- Redaction helpers for sensitive values in logs/realtime payloads.
- Role-based route checks with Flask-Login authentication.

---

## Authorization and Access

Current route behavior:

- `/dashboard`, `/ai-audit`: `Admin` and `Medico`.
- `/historico/historico`, `/scheduling/scheduling`, `/realtime/`: `Admin`, `Medico`, `Atendente`.
- `/ai/test`: authenticated users.
- `/admin/ai-metrics`: authenticated users.

Detailed behavior is documented in `AUTHORIZATION_AND_MULTI_TENANCY.md`.

---

## Tenancy and Clinic Isolation Status

Current repository and migration files do **not** include a `clinic_id` column or a tenancy middleware module.

That means current implementation is a single-tenant operational model at code level. Isolation is not enforced via tenant filters in SQL queries.

This status is documented explicitly so maintainers do not accidentally assume tenant boundary enforcement that does not exist in the current code.

---

## AI Module Summary

The AI module:

1. validates input safety,
2. validates request schema,
3. executes three structured generation stages,
4. validates JSON outputs through schemas,
5. persists an AI audit record with status, token usage, and estimated cost.

Detailed internals are documented in `AI_MODULE_DOCUMENTATION.md`.

---

## Database Summary

Current migration file defines:

- `patients`
- `incoming_messages`
- `message_status_updates`
- `appointments`

Application code additionally relies on:

- `users`
- `ai_audit_logs`

Full table-level documentation is in `DATABASE_SCHEMA.md`.

---

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.app
```

Required runtime variables include:

- DB connection values (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`)
- `SECRET_KEY`
- webhook and integration variables (`VERIFY_TOKEN`, etc.)
- `OPENAI_API_KEY` for AI endpoints

---

## Operational Routes

- `/login` — login page
- `/logout` — logout action (POST)
- `/` — landing page (authenticated)
- `/whoami` — session debug JSON
- `/dashboard` — message analytics dashboard
- `/ai-audit` — AI audit dashboard
- `/admin/ai-metrics` — AI metrics view
- `/realtime/` — realtime UI
- `/realtime/webhook` — WhatsApp webhook endpoint
- `/historico/historico` — message history
- `/scheduling/scheduling` — scheduling workflow
- `/ai/test` — AI processing endpoint

---

## How to Work Safely as a Junior Developer

Before changing any route/service/repository:

1. Confirm auth requirements (`login_required`).
2. Confirm role requirements (`role_required`).
3. Confirm CSRF enforcement for state-changing forms.
4. Confirm SQL queries remain parameterized.
5. Confirm logs do not expose sensitive data.
6. If changing AI flow, ensure audit logging still captures status/tokens/cost.
7. Update documentation files in the same PR.

---

## Glossary

- **Blueprint**: Flask module for grouping related routes.
- **Repository**: module responsible for SQL persistence/retrieval.
- **RBAC**: Role-Based Access Control.
- **CSRF**: protection against forged browser requests.
- **Webhook**: endpoint called by external systems on events.
- **Socket.IO**: real-time push channel between server and browser.
- **Audit log**: persistent record of actions/outcomes for traceability.
- **Token usage**: model billing unit counts from AI provider response.
