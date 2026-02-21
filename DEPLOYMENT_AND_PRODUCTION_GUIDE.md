# DEPLOYMENT_AND_PRODUCTION_GUIDE.md

## 1) Purpose

This guide explains how to deploy and operate the current Cannab'IA Flask application safely in production.

It covers:

- runtime topology,
- security hardening,
- session and proxy behavior,
- rate limiting,
- database operations,
- AI observability,
- release and incident procedures.

---

## 2) Recommended Production Topology

```text
                    Internet
                       |
                       v
            +----------+-----------+
            | Reverse Proxy / LB   |
            | TLS termination      |
            | forwards headers     |
            +----------+-----------+
                       |
                       v
          +------------+-------------+
          | Flask App Instances      |
          | Gunicorn/WSGI + SocketIO |
          +------------+-------------+
                       |
          +------------+------------+
          |                         |
          v                         v
   +------+-------+          +------+----------------+
   | MySQL        |          | External Integrations |
   | app data     |          | WhatsApp / SMTP / AI  |
   +--------------+          +------------------------+
                       |
                       v
            +----------+-----------+
            | Logs / Metrics /     |
            | Alerting backend     |
            +----------------------+
```

---

## 3) Environment Configuration Categories

### Core app

- `SECRET_KEY`
- cookie settings
- request size limits

### Database

- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`

### Integrations

- WhatsApp verification and API credentials
- SMTP credentials
- OpenAI key

### Rate limit

- login and webhook thresholds/windows

Use separate values for dev/staging/prod and never share credentials across environments.

---

## 4) Reverse Proxy and Proxy Header Handling

In production behind reverse proxy/load balancer, ensure request metadata (scheme/ip) is trustworthy.

Why:

- rate limiting uses request IP sources,
- secure-cookie and HTTPS assumptions rely on correct scheme,
- audit logs should represent real client context.

If proxy middleware is added (for example `ProxyFix`), configure trusted hop counts carefully.

---

## 5) Session and Cookie Hardening

Current code configures:

- `SESSION_COOKIE_HTTPONLY = True`
- `SESSION_COOKIE_SAMESITE = "Lax"`
- `SESSION_COOKIE_SECURE = False` in app factory (development-style)

Production practice:

- enforce HTTPS end-to-end,
- set secure cookie behavior appropriately in deployment config,
- rotate `SECRET_KEY` through controlled process when required.

---

## 6) CSRF Protection in Production

Current CSRF token utilities are used in login/logout/scheduling flows.

Production checklist:

1. Ensure every browser form that mutates state has CSRF validation.
2. Ensure tokens are regenerated and invalidated appropriately.
3. Validate CSRF behavior after auth/session changes.

---

## 7) Rate Limiting and Abuse Protection

Current implementation:

- in-memory process-local bucket strategy.

Operational implication:

- counters are not shared across multiple instances.

For scaled deployments:

- plan centralized/distributed limiter backend,
- keep separate limits for login and webhook paths,
- monitor 429 rates for abuse visibility.

---

## 8) Database Operations and Safety

### Migration handling

- migration runner executes SQL statements from migration file.
- ensure migrations are run in staging before production.

### Access model

- use least-privilege DB users,
- do not run app with administrative DB credentials,
- restrict DB network exposure to app hosts.

### Backup and recovery

- encrypted backups,
- periodic restore drills,
- documented RPO/RTO targets.

---

## 9) Logging and Monitoring

Current app logs include:

- request id,
- route path,
- method,
- status,
- elapsed time.

Security utilities provide redaction helper functions.

Monitoring targets:

- 5xx error rates,
- login 401/429 rates,
- webhook 4xx/5xx rates,
- AI error/validation/security-blocked rates,
- AI token and cost trends.

---

## 10) AI Production Operations

For AI endpoints:

- ensure `OPENAI_API_KEY` management is secure,
- monitor audit table growth,
- monitor `estimated_cost_usd` totals,
- alert on abnormal token usage spikes.

Audit data is central to post-incident analysis and budget governance.

---

## 11) Tenancy and Isolation in Deployment

Current codebase does not implement tenant middleware or `clinic_id` query enforcement.

Deployment teams should treat this system as single-tenant at current code state unless a clinic-aware schema and query model is introduced.

---

## 12) Release Procedure

1. Build release artifact.
2. Apply migrations in staging.
3. Validate login/logout/CSRF flows.
4. Validate webhook verification and event processing.
5. Validate dashboard/realtime routes by role.
6. Validate AI endpoint and audit visibility.
7. Deploy to production.
8. Observe logs/metrics closely after rollout.

---

## 13) Rollback Procedure

1. Keep previous deploy artifact available.
2. If release fails, redirect traffic back to previous version.
3. Evaluate migration rollback requirements.
4. Confirm auth/webhook/AI critical paths restored.
5. Capture incident timeline and root cause.

---

## 14) Incident Response Playbook (Concise)

For security or data incidents:

1. Contain impacted endpoints.
2. Collect request ids and timestamps.
3. Pull relevant app logs and AI audit rows.
4. Determine blast radius.
5. Patch and validate.
6. Re-enable traffic gradually.
7. Complete postmortem and documentation updates.

---

## 15) Production Checklist

- [ ] TLS enforced
- [ ] Secrets set from secure store
- [ ] DB least-privilege user configured
- [ ] Migration status verified
- [ ] Login/CSRF tested
- [ ] Webhook verification tested
- [ ] AI audit logging verified
- [ ] Monitoring and alerting active
- [ ] Backup/restore process verified

---

## 16) Glossary

- **TLS termination**: HTTPS decryption at proxy/load balancer.
- **Least privilege**: only minimum permissions required.
- **RPO/RTO**: backup recovery objectives.
- **Postmortem**: structured analysis after incident.
- **429**: HTTP status for rate-limited requests.
