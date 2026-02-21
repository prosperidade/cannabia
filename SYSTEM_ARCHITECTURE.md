# SYSTEM_ARCHITECTURE.md

## 1) Purpose

This document explains the actual architecture present in the current Flask codebase, focusing on practical request flow, component boundaries, and operational behavior.

Audience: junior developers who need a reliable mental model before implementing changes.

---

## 2) Architectural Style

Cannab'IA is organized in layers:

1. **Presentation / Web Layer** (`src/app.py`, `src/web/routes/*`)
2. **Business Layer** (`src/services/*`)
3. **Data Access Layer** (`src/repositories/*`)
4. **Infrastructure Layer** (`src/infra/*`, `src/config.py`)
5. **AI Layer** (`src/ai/*`)
6. **External Integrations** (`src/integrations/*`)

This style is intended to keep route handlers thin and make behavior testable and understandable.

---

## 3) Component Map

```text
+------------------------------------------------------------+
| Flask App Factory (src/app.py)                             |
| - config/session                                           |
| - Flask-Login setup                                        |
| - before_request / after_request                           |
| - register blueprints                                      |
+----------------------+-------------------------------------+
                       |
                       v
      +----------------+------------------------------+
      | Blueprints (src/web/routes)                   |
      | auth helpers, dashboard, scheduling, realtime |
      +----------------+------------------------------+
                       |
                       v
      +----------------+------------------------------+
      | Services (src/services)                       |
      | message_service, appointment_service          |
      +----------------+------------------------------+
                       |
                       v
      +----------------+------------------------------+
      | Repositories (src/repositories)               |
      | SQL operations via db_cursor                  |
      +----------------+------------------------------+
                       |
                       v
                 +-----+------+
                 |   MySQL    |
                 +------------+

AI Path:

route /ai/test -> CannabIAService -> CannabIAPipeline -> OpenAI -> ai_audit_logs
```

---

## 4) Flask Request Lifecycle

### Step 1: Request Entry

Flask receives an HTTP request and matches it to a route.

### Step 2: `before_request`

In `src/app.py`, before every request:

- request start time is recorded,
- a unique request id (`g.request_id`) is created,
- current user id is attached to `g.user_id` when authenticated.

### Step 3: Access Control Decorators

Depending on route:

- `login_required`
- `role_required(...)`
- CSRF checks
- rate-limit checks

### Step 4: Handler Execution

Route handler invokes service/repository logic.

### Step 5: `after_request`

After handler returns:

- elapsed time is measured,
- structured log line is emitted with request metadata.

### Step 6: Response Sent

Response is returned to the browser or external caller.

---

## 5) Session Handling and Authentication Internals

Flask-Login setup includes:

- `LoginManager` initialization,
- `user_loader` callback to load users from DB,
- `AppUser` wrapper implementing `UserMixin`.

Session behavior includes:

- cookie-backed authenticated session,
- `SESSION_COOKIE_HTTPONLY = True`,
- `SESSION_COOKIE_SAMESITE = "Lax"`,
- `SESSION_COOKIE_SECURE = False` in current app factory (development-style value in code).

Login flow:

1. GET serves login template with CSRF token.
2. POST applies rate limit and CSRF validation.
3. User credentials verified via repository + bcrypt.
4. `login_user(...)` establishes session.

Logout flow:

1. POST requires CSRF token.
2. Session is invalidated via `logout_user()` and CSRF tokens cleared.

---

## 6) Route Domain Architecture

## 6.1 Dashboard Domain

- `/dashboard`:
  - ensures message tables,
  - fetches list data,
  - computes aggregates by contact and day,
  - renders chart-oriented template data.

- `/ai-audit`:
  - loads audit summary and recent logs,
  - renders AI audit dashboard.

## 6.2 Realtime Domain

- `/realtime/webhook` GET:
  - performs provider verification using token challenge.

- `/realtime/webhook` POST:
  - rate limit,
  - payload size check,
  - payload structure validation,
  - event parsing and persistence,
  - redacted realtime emission to connected clients.

- Socket connect event:
  - rejects unauthenticated connections.

## 6.3 Scheduling Domain

- `/scheduling/scheduling` supports GET/POST.
- POST path validates CSRF and date format.
- Data persisted through appointment repository.

## 6.4 Historical Messages Domain

- `/historico/historico` fetches message list and renders tabular history.

## 6.5 AI Domain

- `/ai/test` expects JSON.
- Executes AI service orchestration with audit persistence.

---

## 7) AI Architecture in the System Context

```text
HTTP /ai/test
   |
   v
CannabIAService
   |- validate_anamnesis_security
   |- AnamnesisInput schema validation
   |- pipeline.run(...) [3 stages]
   |- calculate_cost(...)
   |- save_ai_audit_log(...)
   v
JSON response
```

The service records outcomes across all major branches (success, validation/security failure, runtime error).

---

## 8) Security-Relevant Cross-Cutting Concerns

1. **CSRF helpers** in `web/routes/auth.py`.
2. **Rate-limiter utility** in-memory in `web/routes/auth.py`.
3. **Role enforcement decorator** in `infra/security.py`.
4. **Sensitive data redaction** helpers in `infra/security.py`.
5. **Payload max size** enforcement for webhook via config value.

---

## 9) Tenancy Architecture Status

Current codebase does not include:

- `src/tenancy.py`,
- tenancy middleware,
- repository-level `clinic_id` filtering.

Current architecture therefore behaves as single-tenant at application data-access level.

---

## 10) Design Trade-offs

### Positives

- Clear separation of route/service/repository concerns.
- Explicit SQL with parameterized placeholders.
- Useful request-level observability metadata.
- AI audit logging integrated into main AI execution path.

### Constraints

- In-memory rate limit is process-local.
- Migration file does not define all tables used by repositories.
- No built-in tenant context/filtering layer in current tree.

---

## 11) Practical Maintenance Guide

When adding a feature, keep this order:

1. Define route and access decorators.
2. Add service-level validation/orchestration.
3. Add repository query with parameterized SQL.
4. Add/confirm migration changes.
5. Add observability and audit where needed.
6. Update architecture + schema docs.

---

## 12) Glossary

- **App Factory**: pattern where Flask app is created by function.
- **`g` context**: per-request storage object in Flask.
- **Blueprint**: route group module.
- **Service Layer**: business rule orchestration layer.
- **Repository Layer**: SQL data access layer.
- **Websocket Event**: real-time server push message.
