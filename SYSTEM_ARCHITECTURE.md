# SYSTEM_ARCHITECTURE.md

## 1) System Overview

Cannab'IA is a modular Flask application organized by layered responsibilities:

- **Web layer**: Blueprints and route handlers
- **Service layer**: Business orchestration and validation
- **Repository layer**: SQL persistence through MySQL connector
- **Integration layer**: WhatsApp and email outbound calls
- **AI layer**: Structured prompt pipeline and schema validation
- **Infrastructure layer**: config, DB connections, security helpers, logging

The architecture favors simplicity and readability for operational teams while still separating concerns.

---

## 2) Layer-by-Layer Explanation

## 2.1 Web Layer (HTTP and Socket Entry Points)

Main Flask app responsibilities:

- Create app object
- Register blueprints
- Configure cookie/session behavior
- Initialize Flask-Login and user loading
- Add request instrumentation (`before_request`, `after_request`)
- Expose top-level routes (`/`, `/login`, `/logout`, `/whoami`, `/ai/test`)

Blueprint responsibilities:

- `realtime_notifications`: webhook endpoints and realtime dashboard
- `scheduling_chain`: appointment UI flow
- `historico_atendimento`: historical message view
- `dashboard`: analytic dashboards and AI audit dashboard
- `ai_admin`: AI metrics dashboard page

## 2.2 Service Layer

- `message_service` parses incoming webhook payloads and applies communication rules.
- `appointment_service` validates scheduling form data and formats datetime for persistence.
- `ai/service.py` orchestrates security validation, schema validation, pipeline execution, and audit logging.

This layer prevents route handlers from becoming too large and keeps business logic centralized.

## 2.3 Repository Layer

Repositories are the only place where SQL is executed.

- Message repository: inbound/status event storage and reporting queries
- Appointment repository: insert/list appointment rows
- User repository: fetch active users and verify bcrypt credentials
- Patient repository: patient creation/get-or-create helper for AI linkage
- AI audit repository: persistent AI execution logs and metrics queries

Design decision:

- Use low-level SQL for full control and transparent behavior.
- Keep SQL explicit and visible for auditability.

## 2.4 Integration Layer

- Outbound WhatsApp template sending
- Outbound email alert sending

Services invoke integrations only after business conditions are met (e.g., critical term detection).

## 2.5 AI Layer

- Prompt templates define strict JSON-only responses.
- Pydantic schemas enforce output contracts.
- Pipeline executes three deterministic stages.
- Security validator blocks obvious prompt injection patterns.
- Pricing utility estimates cost from token usage.

## 2.6 Infrastructure Layer

- `config.py` loads environment variables
- `infra/database.py` creates DB connections and cursor context manager
- `infra/security.py` provides RBAC and sensitive-data redaction
- `infra/logging.py` configures log sinks
- `infra/run_migrations.py` applies SQL migrations

---

## 3) Flask Request Lifecycle in Detail

```text
Client Request
   |
   v
Flask Router -> URL match
   |
   v
before_request:
  - start timer
  - set g.request_id
  - set g.user_id (if authenticated)
   |
   v
Decorators:
  - login_required?
  - role_required?
  - CSRF/rate-limit checks (route-specific)
   |
   v
Route handler
   |
   +--> Service layer (rules)
   |      |
   |      +--> Repository layer (SQL)
   |      +--> Integration layer (external APIs)
   |
   v
after_request:
  - compute elapsed ms
  - structured log line
   |
   v
HTTP response
```

Why `before_request` is important:

- Adds observability metadata (`request_id`) once, globally.
- Helps tie user and request context to downstream operations.

---

## 4) Authentication, Session, and Middleware-like Behavior

Flask does not use a separate middleware stack like some frameworks; instead, common cross-cutting behavior is implemented via:

- `before_request`
- `after_request`
- decorators

Session handling details:

- Flask session cookie stores auth session state used by Flask-Login.
- Cookie hardening settings are configured in app config.
- Login/logout flows include CSRF checks to prevent cross-site request forgery.

Important note:

- In current code, `SESSION_COOKIE_SECURE` is forced `False` inside `create_app`, which is acceptable only for local dev but must be revisited for TLS production deployment.

---

## 5) Realtime and Webhook Architecture

```text
WhatsApp Provider
    |
    | POST /realtime/webhook
    v
realtime_notifications.webhook
    |- rate limit check
    |- payload size check
    |- payload structure check
    |- parse field type
    |- handle_message_event / handle_status_event
    |- persist to DB
    |- socketio.emit(redacted_payload)
    v
Authenticated browser dashboard receives event
```

Design decisions:

- Keep webhook parsing shallow but explicit.
- Emit redacted payload to reduce exposure risk in front-end channels.
- Use per-route checks rather than implicit global behavior.

---

## 6) AI Processing Architecture

```text
POST /ai/test
   |
   v
CannabIAService.process_patient_case
   |- get request/user context from flask.g
   |- resolve patient_id
   |- security validation (prompt injection patterns)
   |- schema validation (AnamnesisInput)
   |- run pipeline (3 LLM stages)
   |- aggregate token usage
   |- estimate USD cost
   |- persist ai_audit_logs
   v
JSON response
```

The audit-first design ensures both successful and failed AI requests are traceable.

---

## 7) Architecture Constraints and Current Trade-offs

1. **Single-process assumptions**
   - In-memory rate limiter buckets are process-local.
   - Not suitable as-is for horizontally scaled production.

2. **Partial schema evolution**
   - Migration SQL and runtime-created tables are not fully aligned.

3. **Tenant isolation not enforced in repository SQL**
   - Multi-clinic model is documented as a required pattern, not fully implemented.

4. **Direct SQL without ORM**
   - Good transparency, but developers must manually enforce every safety filter.

---

## 8) Safe Extension Blueprint

When adding a new feature:

1. Add route in web layer with explicit auth + role checks.
2. Add business rules in service layer.
3. Add SQL in repository with explicit parameterized queries.
4. If feature is clinic-scoped, enforce `clinic_id` filtering in **every** SELECT/UPDATE/DELETE.
5. Add audit logging for security-sensitive operations.
6. Add docs update in all relevant documentation files.

---

## 9) Glossary (Simple Terms)

- **Blueprint**: Flask module grouping related routes.
- **Decorator**: Function wrapper adding checks like login/role.
- **RBAC**: Role-Based Access Control; permissions based on user role.
- **Tenant**: A clinic/customer logically isolated in shared infrastructure.
- **PHI**: Protected Health Information.
- **Webhook**: HTTP endpoint called by an external system when events happen.
- **Idempotency**: Processing an event once even if it arrives multiple times.
- **Request context (`g`)**: Per-request storage object in Flask.
- **Repository pattern**: Dedicated data-access module keeping SQL out of route handlers.
