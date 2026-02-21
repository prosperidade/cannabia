# AUTHORIZATION_AND_MULTI_TENANCY.md

## 1) Objective

This document explains two related topics:

1. How authorization is implemented in the current Flask code.
2. What tenancy (multi-clinic) behavior currently exists in the code and repositories.

Audience: junior developers responsible for safe access control and data isolation decisions.

---

## 2) Authentication Mechanism

Authentication is implemented with Flask-Login:

- `LoginManager` is initialized in `src/app.py`.
- User identity is loaded using `user_repository.get_user_by_id`.
- Login POST verifies bcrypt password hash from `users.password_hash`.
- Authenticated identity is stored in session cookie.

Authentication status can be inspected at `/whoami`.

---

## 3) Authorization (RBAC) Mechanism

Authorization is implemented with a role decorator:

- `role_required(*allowed_roles)` in `src/infra/security.py`.

Decorator behavior:

1. Requires authenticated session (`login_required`).
2. Reads `current_user.role`.
3. Returns 403 if role missing or not in allowed list.

Roles used in route decorators:

- `Admin`
- `Medico`
- `Atendente`

---

## 4) Route Access Matrix (Current Code)

| Route | Auth Required | Role Required |
|---|---|---|
| `/` | Yes | No explicit role check |
| `/dashboard` | Yes | Admin, Medico |
| `/ai-audit` | Yes | Admin, Medico |
| `/historico/historico` | Yes | Admin, Medico, Atendente |
| `/scheduling/scheduling` | Yes | Admin, Medico, Atendente |
| `/realtime/` | Yes | Admin, Medico, Atendente |
| `/ai/test` | Yes | No explicit role check |
| `/admin/ai-metrics` | Yes | No explicit role check |

This matrix is important for maintenance: route-level decorators are the real authorization gate.

---

## 5) CSRF and Authorization Interaction

CSRF is not RBAC, but both protect sensitive actions.

Current CSRF-protected actions include:

- login POST,
- logout POST,
- scheduling POST.

Why both matter:

- RBAC checks who is allowed.
- CSRF checks whether the browser request is legitimate and intentional.

---

## 6) Session Context and Request Context

For each request, `before_request` populates:

- `g.request_id`
- `g.user_id` (if authenticated)

This context is reused in AI audit logs (`user_id`, `request_id`) to maintain traceability across modules.

---

## 7) Multi-Tenancy / Clinic Isolation Status in Current Tree

Current codebase inspection shows:

- no `src/tenancy.py` module,
- no tenancy middleware registration,
- no `tenancy_repository` module,
- no repository method signatures requiring `clinic_id`,
- no SQL tenant filtering (`WHERE clinic_id = ...`) in repositories,
- migration schema does not define `clinic_id` columns.

Therefore, current implementation is **single-tenant at application data-access level**.

---

## 8) Why This Status Must Be Explicit

A common risk in healthcare systems is assuming tenant isolation exists when it does not.

If developers assume invisible clinic filtering is happening but queries are global, accidental cross-clinic leakage can occur when multi-clinic data is introduced.

This document exists to prevent that misunderstanding.

---

## 9) Secure vs Insecure Query Examples

Even in single-tenant mode, secure query construction rules still apply.

### Secure (parameterized)

```sql
SELECT * FROM incoming_messages WHERE sender = %s ORDER BY id DESC
```

### Insecure (string interpolation)

```sql
SELECT * FROM incoming_messages WHERE sender = '" + sender + "' ORDER BY id DESC
```

The insecure pattern is vulnerable to injection.

---

## 10) If Clinic Isolation Is Introduced in Future Migrations

When clinic-aware tenancy is added, every tenant-owned table should include `clinic_id` and every read/write query should filter by it.

Example secure clinic-aware pattern:

```sql
SELECT id, message_text
FROM incoming_messages
WHERE clinic_id = %s
ORDER BY id DESC;
```

Example insecure clinic-aware anti-pattern:

```sql
SELECT id, message_text
FROM incoming_messages
ORDER BY id DESC;
```

Without `clinic_id` filter, multi-clinic data can leak.

---

## 11) Practical Authorization Review Checklist

Before merging any access-related change:

1. Does route have correct `login_required`/`role_required` decorators?
2. Does action include CSRF check for browser form POST?
3. Is `current_user.role` checked against policy matrix?
4. Does endpoint reveal sensitive data without explicit need?
5. Does auditing capture enough context (`user_id`, `request_id`)?

---

## 12) Glossary

- **Authentication**: proving who the user is.
- **Authorization**: deciding what the user may do.
- **RBAC**: role-based permission control.
- **Session**: server-recognized login state for browser user.
- **Tenant isolation**: preventing one clinic/customer from seeing another’s data.
- **CSRF**: protection against forged browser requests.
