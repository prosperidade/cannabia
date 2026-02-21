# AUTHORIZATION_AND_MULTI_TENANCY.md

## 1) Why This Document Exists

Healthcare systems are high-risk systems. The two most dangerous classes of authorization mistakes are:

1. **Privilege mistakes** (a user can do more than they should)
2. **Tenant isolation mistakes** (a clinic can see another clinic's data)

This document explains the current RBAC behavior and how to implement/maintain safe multi-clinic isolation.

---

## 2) Current Authorization Model in Code

Authentication:

- Flask-Login session authentication
- User loaded from `users` table with `is_active = 1`

RBAC:

- Decorator `role_required(*allowed_roles)` checks user role.
- Roles in use:
  - `Admin`
  - `Medico`
  - `Atendente`

Route-level access currently observed:

- `/dashboard` and `/ai-audit`: `Admin`, `Medico`
- `/historico`, `/scheduling`, `/realtime/`: `Admin`, `Medico`, `Atendente`
- `/ai/test`: login required (no explicit role decorator)
- `/admin/ai-metrics`: login required (no explicit role decorator)

Important implication:

- Access control is mostly role-based, but some routes rely only on authentication.

---

## 3) Global Roles vs Clinic Roles (Conceptual Model)

To support multi-clinic safely, distinguish:

1. **Global role**: system-wide power (example: platform super-admin)
2. **Clinic role**: role inside one clinic only

Example:

- A doctor can be `Medico` in clinic A but have no access to clinic B.
- A global admin may access all clinics for operations/support.

Recommended mapping model:

```text
users
  id, ...

clinics
  id, name, ...

user_clinic_roles
  user_id, clinic_id, clinic_role

(optional) global_roles
  user_id, global_role
```

This avoids storing one flat role that cannot represent per-clinic differences.

---

## 4) What Multi-Tenancy Means Here

Multi-tenancy in this context means:

- Same application deployment serves many clinics.
- Data is logically isolated by `clinic_id`.
- Every query, update, and report is scoped to one clinic unless global permission explicitly allows broader scope.

### 4.1 Isolation Rule (Golden Rule)

> If a table stores clinic-owned data, every access path must enforce `clinic_id`.

No exceptions for:

- list endpoints
- search endpoints
- dashboard aggregates
- exports
- background jobs
- AI logs

---

## 5) Secure vs Insecure Authorization Patterns

### 5.1 Secure pattern

```python
# Pseudocode
user = current_user
clinic_id = get_current_clinic_id_from_session_or_route()
assert user_has_clinic_access(user.id, clinic_id)
rows = repo.list_messages(clinic_id=clinic_id)
```

Why secure:

- Access check and data filter both use clinic context.

### 5.2 Insecure pattern

```python
# Pseudocode
rows = repo.list_messages()  # no clinic filter
```

Why insecure:

- Any authenticated user may retrieve cross-clinic rows.

### 5.3 Secure SQL pattern

```sql
UPDATE appointments
SET status = %s
WHERE id = %s
  AND clinic_id = %s;
```

### 5.4 Insecure SQL pattern

```sql
UPDATE appointments
SET status = %s
WHERE id = %s;
```

The insecure query allows modifying another clinic’s row if ID is guessed.

---

## 6) `clinic_id` Isolation: Step-by-Step Enforcement

For each new or existing tenant-owned table:

1. Add `clinic_id` NOT NULL.
2. Add FK to `clinics(id)` if table exists.
3. Add index on `clinic_id`.
4. Add composite indexes by access patterns.
5. Update repository function signatures to require `clinic_id`.
6. Reject calls without clinic context.
7. Add automated tests for cross-tenant non-visibility.

Example repository signature pattern:

```python
def list_messages(clinic_id: int, sender: str | None = None):
    ...
```

Avoid optional `clinic_id=None` defaults in tenant-owned queries.

---

## 7) Session and Clinic Context

Session should include (or route should carry) current clinic context:

- authenticated user id
- active clinic id
- optionally clinic role

Validation flow per request:

1. confirm user authenticated
2. resolve active clinic context
3. verify user membership in clinic
4. apply RBAC decision (clinic role or global role)
5. execute DB query with `clinic_id`

Without step 3 + 5, tenant isolation is incomplete.

---

## 8) Testing for Cross-Tenant Leakage

## 8.1 Minimum automated tests

1. Create clinic A and clinic B.
2. Create users scoped to each clinic.
3. Insert records for both clinics.
4. Authenticate as clinic A user.
5. Hit every endpoint (including dashboard aggregates).
6. Assert only clinic A records appear.
7. Repeat for write operations and AI audit views.

## 8.2 Manual penetration-style checks

- Try changing URL params/record IDs to known rows from another clinic.
- Confirm API returns 404/403 and does not leak row existence details.
- Validate no cross-tenant data appears in websocket payloads.

## 8.3 SQL integrity checks

Run periodic checks for invalid links where child/parent clinic differs.

---

## 9) RBAC Decision Matrix Example

| Action | Atendente | Medico | Admin | Global Admin |
|---|---:|---:|---:|---:|
| View clinic messages | ✅ | ✅ | ✅ | ✅ |
| Send template response | ✅ | ✅ | ✅ | ✅ |
| View AI cost dashboard | ❌ | ✅ | ✅ | ✅ |
| Manage users inside clinic | ❌ | ❌ | ✅ | ✅ |
| Access all clinics | ❌ | ❌ | ❌ | ✅ |

Use this matrix as policy documentation and keep route decorators aligned.

---

## 10) Common Mistakes to Avoid

1. Filtering list queries but forgetting count/sum queries.
2. Enforcing role checks without clinic membership checks.
3. Using user role from session without re-validating active clinic context.
4. Logging raw payloads that include PHI from other tenants.
5. Assuming UI filtering is security (it is not).

---

## 11) Glossary

- **Tenant isolation**: preventing one customer/clinic from accessing another’s data.
- **Clinic scope**: permissions and data boundaries tied to one clinic.
- **Global role**: role that can cross clinic boundaries.
- **Least privilege**: grant only minimum permissions required.
- **Horizontal privilege escalation**: access another peer’s data at same privilege level.
