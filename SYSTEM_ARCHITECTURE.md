# SYSTEM_ARCHITECTURE.md

## 1) Overview

Cannab'IA is a modular Flask application with clear separation between web routes, business logic, repository SQL access, integrations, and AI pipeline orchestration.

Primary goal of architecture: keep behavior understandable and traceable for healthcare operations.

---

## 2) Architectural Layers

## 2.1 Web Layer (`src/app.py`, `src/web/routes/*`)

Responsibilities:

- initialize Flask application,
- register blueprints,
- expose HTTP endpoints,
- apply request-level context (`before_request`/`after_request`),
- enforce auth and role checks through decorators.

## 2.2 Service Layer (`src/services/*`, `src/ai/service.py`)

Responsibilities:

- orchestrate workflow rules,
- validate domain inputs,
- call repositories and integrations in safe sequence.

## 2.3 Repository Layer (`src/repositories/*`)

Responsibilities:

- execute parameterized SQL queries only,
- centralize data persistence/retrieval,
- expose table-focused access functions.

## 2.4 Infrastructure Layer (`src/infra/*`, `src/config.py`)

Responsibilities:

- DB connection/cursor context management,
- logging configuration,
- security helper functions (RBAC, redaction),
- migration execution support,
- environment variable management.

## 2.5 Integrations (`src/integrations/*`)

Responsibilities:

- outbound WhatsApp template calls,
- outbound SMTP email notifications.

## 2.6 AI Layer (`src/ai/*`)

Responsibilities:

- prompt templates,
- schema enforcement,
- model execution,
- token/cost calculations,
- stage orchestration.

---

## 3) Component Interaction Diagram

```text
+----------------------------+
| Browser / API caller       |
+-------------+--------------+
              |
              v
+-------------+---------------------------------------+
| Flask app (app.py)                                  |
| - auth/session setup                                |
| - before_request / after_request                    |
| - top-level routes                                  |
+-------------+---------------------------------------+
              |
      +-------+------------------------+
      | Blueprints (web/routes)        |
      +-------+------------------------+
              |
      +-------+------------------------+
      | Services                        |
      | appointment / message / AI svc  |
      +-------+------------------------+
              |
      +-------+------------------------+
      | Repositories                    |
      | SQL operations via db_cursor    |
      +-------+------------------------+
              |
              v
          +---+---+
          | MySQL |
          +-------+

Parallel external flows:
- Webhook provider -> realtime route
- AI service -> OpenAI API
- Message service -> WhatsApp / Email integrations
```

---

## 4) Detailed Request Lifecycle

### Step 1: Routing

Incoming request is mapped to endpoint by Flask router.

### Step 2: Pre-processing (`before_request`)

Global pre-processing in `src/app.py`:

- timer start is recorded,
- request UUID is attached to `g.request_id`,
- current authenticated user id is attached to `g.user_id`.

### Step 3: Access and protection checks

Depending on endpoint, one or more checks run:

- `login_required`,
- `role_required`,
- CSRF validation,
- rate limiting,
- payload shape/size checks.

### Step 4: Core handler execution

Handler calls services and repositories.

### Step 5: Post-processing (`after_request`)

- elapsed time computed,
- request metadata logged.

### Step 6: Response to client

Client receives HTML or JSON response.

---

## 5) Authentication and Session Architecture

### Components

- `LoginManager` from Flask-Login
- `AppUser` wrapper object
- `user_loader` callback querying `user_repository`

### Login flow architecture

```text
GET /login -> render form with CSRF token
POST /login
  -> rate limit check
  -> CSRF validation
  -> user lookup in users table
  -> bcrypt password verify
  -> login_user(AppUser)
  -> redirect to index
```

### Logout flow architecture

```text
POST /logout
  -> CSRF validation
  -> logout_user()
  -> clear CSRF session keys
  -> redirect login
```

---

## 6) Route-Domain Architecture

## 6.1 Messaging/Realtime domain

- Webhook endpoint receives external event payloads.
- Message service parses and persists message/status updates.
- Redacted event payload is emitted to connected realtime clients.

## 6.2 Dashboard domain

- Message listing and aggregate queries generate chart/table datasets.
- AI audit summary and recent logs are fetched for dashboard views.

## 6.3 Scheduling domain

- Input validated in service layer.
- Date normalized for SQL storage.
- Data persisted in appointments table.

## 6.4 AI domain

- Input is validated and passed through 3-stage pipeline.
- Output and metadata are persisted in AI audit table.

---

## 7) AI Architecture in Context

```text
/ai/test route
   -> CannabIAService
      -> security validation
      -> schema validation
      -> CannabIAPipeline
         stage 1: clinical analysis
         stage 2: treatment plan
         stage 3: scientific report
      -> token aggregation
      -> cost estimation
      -> ai_audit_logs write
```

This flow ensures operational observability (status + token/cost metrics).

---

## 8) Security-Critical Cross-Cutting Concerns

1. CSRF helper functions in `web/routes/auth.py`.
2. In-memory rate limiting in `web/routes/auth.py`.
3. Role decorator in `infra/security.py`.
4. Sensitive data redaction helper in `infra/security.py`.
5. Request size limit via app config and webhook checks.

---

## 9) Multi-Clinic / Tenancy Architecture Status

From current codebase structure and SQL usage:

- no `src/tenancy.py`,
- no tenancy middleware registration,
- no tenancy repository module,
- no `clinic_id` enforced query patterns in repositories,
- no `clinic_id` columns in current migration.

Therefore, current runtime architecture is single-tenant at data-access level.

---

## 10) Operational Traceability Model

Traceability fields propagated in request/AI flow:

- `g.request_id` for request correlation,
- `g.user_id` for actor context,
- AI audit fields for status/tokens/cost.

This allows incident analysis from request logs to AI audit records.

---

## 11) Safe Extension Pattern

When adding a new feature:

1. Add route and explicit access decorators.
2. Add service orchestration/validation.
3. Add repository SQL using parameter placeholders.
4. Add/update migrations if schema changes.
5. Add audit/observability where relevant.
6. Update docs in this architecture suite.

---

## 12) Glossary

- **Decorator**: function wrapper adding behavior to route handlers.
- **Request Context (`g`)**: per-request storage object.
- **Service Layer**: business-flow orchestration layer.
- **Repository Pattern**: data-access isolation layer.
- **Cross-cutting concern**: concern affecting many routes (security/logging).
