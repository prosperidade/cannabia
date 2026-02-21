# Cannab'IA — Production Flask Application Documentation

Cannab'IA is a Flask-based clinical operations platform that combines:

- Patient communication intake (WhatsApp webhook)
- Real-time operational dashboards (Flask + Socket.IO)
- Scheduling workflows
- Basic role-based access control (RBAC)
- AI-assisted clinical analysis pipeline with audit and cost tracking
- MySQL persistence with repository-based SQL access

This README is intentionally written for junior developers. It explains not only **what** exists, but also **why** each part exists and how to evolve it safely.

---

## 1) Quick Orientation (Start Here)

If you are new to this codebase, read in this order:

1. `README.md` (this file)
2. `SYSTEM_ARCHITECTURE.md`
3. `DATABASE_SCHEMA.md`
4. `AUTHORIZATION_AND_MULTI_TENANCY.md`
5. `AI_MODULE_DOCUMENTATION.md`
6. `DEPLOYMENT_AND_PRODUCTION_GUIDE.md`

This order goes from broad context to deep operational details.

---

## 2) What Problem the System Solves

Cannab'IA helps a clinic team receive patient communication, organize care workflows, and support medical reasoning with AI outputs.

At a high level:

1. External events arrive through WhatsApp webhook endpoints.
2. Messages are persisted in MySQL.
3. Operators view dashboards (historical + real-time).
4. AI endpoint can process anamnesis JSON and return structured outputs.
5. Every AI call is logged in an audit table with status, token counts, and estimated costs.

---

## 3) High-Level Architecture

```text
                    +--------------------------+
                    |  WhatsApp Cloud Webhook |
                    +------------+-------------+
                                 |
                                 v
+----------------------+   +-----+--------------------+
| Browser (Clinic User)|<->| Flask App (Blueprints)  |
| login/session/csrf   |   | routes + before_request |
+----------+-----------+   +-----+--------------------+
           |                       |
           |                       +-----------------------------+
           |                                                     |
           v                                                     v
+----------------------+                               +---------------------+
| Flask-SocketIO       |                               | AI Service/Pipeline |
| realtime events      |                               | validation + model  |
+----------+-----------+                               +----------+----------+
           |                                                      |
           v                                                      v
      +----+------------------------+                   +---------+----------+
      | MySQL repositories          |<------------------| AI Audit Repository|
      | users/messages/appointments |                   | logs, tokens, cost |
      +-----------------------------+                   +--------------------+
```

---

## 4) Request Lifecycle (Flask)

Every HTTP request follows this lifecycle:

1. **Request arrives** at a Flask route.
2. `before_request` runs:
   - starts request timer
   - creates `g.request_id`
   - stores authenticated `g.user_id` when available
3. Route-level decorators run (`login_required`, `role_required`, custom checks).
4. Route handler executes business logic via services/repositories.
5. `after_request` logs path/method/status/elapsed time.
6. Response is returned to client.

Why this matters:

- `g.request_id` lets you connect AI logs and HTTP logs.
- Centralized timing and user context improve traceability.

---

## 5) Main Feature Areas

### 5.1 Authentication and Session

- Flask-Login manages user sessions.
- Login form is CSRF-protected.
- Passwords are verified using bcrypt hashes.
- Session cookie protections include `HttpOnly` and `SameSite`.

### 5.2 RBAC

Roles currently used:

- `Admin`
- `Medico`
- `Atendente`

Route decorators enforce role checks.

### 5.3 Webhook + Realtime

- `GET /realtime/webhook`: provider verification challenge.
- `POST /realtime/webhook`: receives inbound events.
- Payload is shape-validated, rate-limited, and size-limited.
- Valid events are persisted and emitted to authenticated Socket.IO clients.

### 5.4 Scheduling

- `GET/POST /scheduling/scheduling`
- CSRF-protected form
- Service parses date format and persists appointment

### 5.5 AI Pipeline

- `POST /ai/test`
- Requires login
- Validates payload and anti-prompt-injection signals
- Runs 3-step pipeline:
  1) clinical analysis
  2) treatment plan
  3) scientific report
- Persists AI audit log including token usage and estimated cost

---

## 6) Multi-Tenancy Status (Important)

Current state in code:

- The live schema and repositories operate as **single-tenant by default**.
- There is no enforced `clinic_id` filter in repository SQL.

This means:

- Current production safety depends on deployment/operational boundaries.
- True multi-clinic isolation must be added carefully using the patterns documented in `AUTHORIZATION_AND_MULTI_TENANCY.md`.

Do **not** assume automatic tenant isolation currently exists.

---

## 7) Key Security Controls in Place

- CSRF protection on sensitive forms
- Login/webhook basic rate limiting (in-memory)
- Request size limit (`MAX_CONTENT_LENGTH`)
- Role-based route restrictions
- Socket connection blocked for anonymous users
- Sensitive value redaction utilities for logs/events

Security controls still requiring stronger production hardening are documented in `DEPLOYMENT_AND_PRODUCTION_GUIDE.md`.

---

## 8) Project Structure

```text
src/
  app.py                       # Flask app factory and core routes
  config.py                    # environment configuration
  infra/
    database.py                # MySQL connection/context manager
    logging.py                 # logging setup
    run_migrations.py          # SQL migration runner
    security.py                # RBAC + log redaction helpers
  web/routes/
    auth.py                    # CSRF + rate limit utility functions
    dashboard.py               # dashboard and ai-audit views
    ai_admin.py                # AI metrics page
    historico_atendimento.py   # message history page
    scheduling_chain.py        # scheduling form/listing
    realtime_notifications.py  # webhook + realtime dashboard
  services/
    message_service.py
    appointment_service.py
  repositories/
    user_repository.py
    patient_repository.py
    message_repository.py
    appointment_repository.py
    ai_audit_repository.py
  ai/
    service.py
    pipeline.py
    chains.py
    validators.py
    schemas.py
    prompts.py
    pricing.py
```

---

## 9) Running Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.app
```

Required environment variables include database credentials, `SECRET_KEY`, and optional integration/API keys.

---

## 10) Safe Change Rules (Junior Developer Checklist)

Before editing any SQL query or route:

1. Confirm authentication requirement (`login_required`).
2. Confirm authorization requirement (`role_required`).
3. Confirm tenant filtering strategy (even if tenant model is still evolving).
4. Confirm CSRF behavior for forms.
5. Confirm logging does not leak secrets/PHI.
6. Add/update documentation in the matching architecture/security files.

If you skip these checks, you risk data leakage or privilege escalation.

---

## 11) Documentation Index

- `SYSTEM_ARCHITECTURE.md` — complete technical flow and components
- `DATABASE_SCHEMA.md` — table-by-table schema explanation, keys, indexes, query patterns
- `AUTHORIZATION_AND_MULTI_TENANCY.md` — RBAC and tenant isolation model
- `AI_MODULE_DOCUMENTATION.md` — AI lifecycle, telemetry, safety, and costs
- `DEPLOYMENT_AND_PRODUCTION_GUIDE.md` — secure deployment and production hardening
