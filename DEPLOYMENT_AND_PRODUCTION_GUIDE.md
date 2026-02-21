# DEPLOYMENT_AND_PRODUCTION_GUIDE.md

## 1) Objective

This guide explains how to deploy and operate the current Cannab'IA Flask application in production with strong operational discipline.

It covers topology, security posture, runtime controls, observability, and release process.

---

## 2) Recommended Production Topology

```text
                                Internet
                                   |
                                   v
                    +--------------+---------------+
                    | Reverse Proxy / Load Balancer|
                    | TLS termination + routing    |
                    +--------------+---------------+
                                   |
                                   v
                    +--------------+---------------+
                    | Flask app instances          |
                    | (WSGI workers + Socket.IO)   |
                    +--------------+---------------+
                                   |
                 +-----------------+-------------------+
                 |                                     |
                 v                                     v
          +------+--------+                    +-------+----------------+
          | MySQL         |                    | External services      |
          | app data      |                    | WhatsApp / SMTP / OpenAI|
          +------+--------+                    +-------+----------------+
                 |
                 v
        +--------+----------------+
        | Central logs/metrics    |
        | alerts + incident view  |
        +-------------------------+
```

---

## 3) Environment Management

Separate environments should exist at minimum:

- development,
- staging,
- production.

### Required environment categories

1. **Application security**: `SECRET_KEY`, cookie behavior.
2. **Database access**: host/port/user/password/database.
3. **Webhook/integration settings**: verification token and provider credentials.
4. **AI config**: OpenAI key.
5. **Rate-limit thresholds**: login and webhook limits/windows.

Never reuse production secrets in non-production environments.

---

## 4) Reverse Proxy and Header Trust

Because app runs behind proxy/LB in production, ensure:

- trusted forwarding of client IP/protocol,
- correct TLS/HTTPS awareness,
- consistent behavior for auth cookies and request logging.

If proxy adaptation middleware is introduced (e.g., `ProxyFix`), configure trusted hops carefully.

---

## 5) Session and Cookie Hardening

Current app sets:

- `SESSION_COOKIE_HTTPONLY = True`
- `SESSION_COOKIE_SAMESITE = "Lax"`
- `SESSION_COOKIE_SECURE = False` in app factory

Production deployment should enforce HTTPS transport and secure operational cookie policy.

---

## 6) CSRF in Production

Current form-based sensitive actions use CSRF checks.

Operational guidance:

1. test login/logout/scheduling CSRF behavior in staging every release,
2. verify token handling under real proxy/cookie settings,
3. ensure all future form mutations include CSRF validation.

---

## 7) Rate Limiting and Abuse Control

Current limiter is in-memory and process-local.

Implications:

- counters are not shared across multiple app instances,
- behavior differs under horizontal scaling.

Monitoring signals to watch:

- spikes in 429 responses,
- repeated login brute-force patterns,
- webhook burst anomalies.

---

## 8) Database Operations

### 8.1 Migration execution

- migration runner executes SQL statements from migration file.
- run migration validation in staging before production rollout.

### 8.2 DB credential model

- use least-privilege DB account for app,
- deny unnecessary DDL/admin privileges,
- restrict DB network path to app hosts.

### 8.3 Backup and restoration

- encrypted backups,
- periodic restore tests,
- documented recovery procedures and ownership.

---

## 9) Logging, Monitoring, and Alerting

Current app request logs include:

- request id,
- path/method,
- status code,
- elapsed milliseconds.

Security helper provides data redaction utilities.

Production observability should track:

1. HTTP 5xx rate,
2. login 401/429 patterns,
3. webhook processing failures,
4. AI security/validation/runtime failures,
5. AI token and cost trends over time.

---

## 10) AI Production Operations

### Key operational points

- protect API key management,
- monitor AI audit table volume,
- monitor cost drift and usage spikes,
- periodically review failure category distribution.

### AI audit importance

AI audit records are primary source for:

- incident investigation,
- cost governance,
- model behavior traceability.

---

## 11) Tenant Isolation in Deployment Context

Current codebase does not include tenant middleware or `clinic_id` SQL enforcement.

Therefore, operational deployment should be treated as single-tenant unless schema/query layer is explicitly tenantized in future code/migrations.

---

## 12) Release Workflow

1. Build release artifact.
2. Apply and validate migrations in staging.
3. Run smoke tests for auth/CSRF/realtime/webhook.
4. Run AI endpoint and dashboard checks.
5. Deploy production gradually.
6. Monitor logs/alerts closely post-release.

---

## 13) Rollback Workflow

1. Maintain previous deploy artifact.
2. Roll traffic back on critical regression.
3. Verify DB compatibility state.
4. Re-test critical paths:
   - login/logout,
   - webhook ingestion,
   - dashboard loading,
   - AI endpoint and audit writes.
5. Document timeline and root cause.

---

## 14) Incident Response Framework

If security/data incident occurs:

1. contain affected endpoint(s),
2. capture request IDs and timestamps,
3. gather app logs and AI audit records,
4. determine blast radius,
5. remediate and validate,
6. re-enable traffic safely,
7. publish post-incident report.

---

## 15) Production Readiness Checklist

- [ ] TLS enforced end-to-end
- [ ] production secrets loaded securely
- [ ] least-privilege DB account in use
- [ ] migration state verified
- [ ] CSRF/auth flows validated
- [ ] webhook validation path tested
- [ ] AI audit logging confirmed
- [ ] central monitoring/alerts active
- [ ] backup restore drill completed

---

## 16) Glossary

- **Load Balancer**: distributes incoming traffic across app instances.
- **TLS termination**: HTTPS decryption point at edge proxy.
- **Least privilege**: minimum required permissions only.
- **Smoke test**: fast post-deploy validation of critical functionality.
- **Postmortem**: structured write-up after incident.
