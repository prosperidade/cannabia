# AUTHORIZATION_AND_MULTI_TENANCY.md

## 1) Purpose

This document explains:

1. How authentication and role-based authorization work in current code.
2. How multi-clinic (tenant) isolation is handled in current code.
3. How to reason about secure vs insecure access/query patterns.

---

## 2) Authentication Flow (Current)

Authentication uses Flask-Login.

### Login sequence

1. User opens `/login`.
2. Form includes CSRF token.
3. POST `/login` executes:
   - login rate-limit check,
   - CSRF validation,
   - user lookup in `users` table,
   - bcrypt password verification,
   - session login via `login_user(...)`.

### Session reload sequence

For authenticated requests, Flask-Login `user_loader`:

- receives session user id,
- fetches active user from `users` table (`is_active = 1`),
- loads role into `current_user.role`.

---

## 3) Authorization (RBAC) Flow (Current)

RBAC is implemented via `role_required(*allowed_roles)` decorator.

Behavior:

1. Requires authenticated user.
2. Reads `current_user.role`.
3. Rejects missing role with 403.
4. Rejects disallowed role with 403.
5. Allows request when role is in allowed set.

Roles currently used:

- `Admin`
- `Medico`
- `Atendente`

---

## 4) Current Route Access Matrix

| Route | Authentication | Role policy |
|---|---|---|
| `/` | required | no explicit role gate |
| `/dashboard` | required | Admin, Medico |
| `/ai-audit` | required | Admin, Medico |
| `/historico/historico` | required | Admin, Medico, Atendente |
| `/scheduling/scheduling` | required | Admin, Medico, Atendente |
| `/realtime/` | required | Admin, Medico, Atendente |
| `/ai/test` | required | no explicit role gate |
| `/admin/ai-metrics` | required | no explicit role gate |

---

## 5) CSRF and Authorization Together

CSRF and RBAC solve different problems:

- RBAC answers: “is this user allowed?”
- CSRF answers: “is this browser request legitimate?”

Current CSRF-protected form actions include:

- login POST,
- logout POST,
- scheduling POST.

---

## 6) Request Context for Auditability

`before_request` attaches:

- `g.request_id`,
- `g.user_id` (if authenticated).

AI service reuses these values in audit logs to tie request/action/actor together.

---

## 7) Multi-Clinic / Tenant Isolation Reality in Current Code

After inspecting current repository tree and SQL:

- there is no `src/tenancy.py`,
- there is no tenancy middleware registration,
- there is no `tenancy_repository` module,
- repository methods do not accept mandatory `clinic_id`,
- SQL queries do not enforce `WHERE clinic_id = ...`,
- migration schema does not define `clinic_id` fields.

### Conclusion

Current implementation is single-tenant in application-level data access.

---

## 8) Why Explicit Tenant Status Is Critical

In healthcare systems, implicit assumptions are dangerous.

If engineers believe clinic filters exist when they do not:

- future multi-clinic data imports can create accidental cross-clinic visibility,
- dashboards and aggregate queries can leak data across boundaries,
- audits become harder to interpret safely.

Explicit documentation prevents this class of operational failure.

---

## 9) Secure vs Insecure Query Patterns

### SQL injection-safe pattern (current style)

```sql
SELECT * FROM incoming_messages WHERE sender = %s ORDER BY id DESC
```

### SQL injection-unsafe pattern

```sql
SELECT * FROM incoming_messages WHERE sender = '" + sender + "' ORDER BY id DESC
```

### Tenant-safe pattern (conceptual for future tenantized schema)

```sql
SELECT id, message_text
FROM incoming_messages
WHERE clinic_id = %s
ORDER BY id DESC;
```

### Tenant-unsafe pattern (conceptual)

```sql
SELECT id, message_text
FROM incoming_messages
ORDER BY id DESC;
```

---

## 10) Secure vs Insecure Access Patterns

### Secure access pattern

```text
Authenticate user
-> Apply role_required policy
-> Validate CSRF for form mutations
-> Execute parameterized SQL
-> Record request/audit context
```

### Insecure access pattern

```text
No role checks
-> No CSRF validation for browser POST
-> Interpolated SQL strings
-> No traceability fields
```

---

## 11) Cross-Tenant Leakage Test Guidance (If Tenantization Is Added)

1. Seed clinic A and clinic B data.
2. Authenticate as clinic A user.
3. Verify list/search/dashboard endpoints return only clinic A data.
4. Verify updates/deletes cannot affect clinic B records.
5. Verify websocket events are clinic-scoped.
6. Verify AI audit views are clinic-scoped.

---

## 12) Glossary

- **Authentication**: proving identity.
- **Authorization**: enforcing allowed actions.
- **RBAC**: role-based access decisions.
- **Tenant isolation**: preventing one customer/clinic from seeing another’s data.
- **CSRF**: browser request forgery protection.
- **Privilege escalation**: gaining access beyond intended permissions.
