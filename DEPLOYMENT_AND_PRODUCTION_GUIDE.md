# DEPLOYMENT_AND_PRODUCTION_GUIDE.md

## 1) Deployment Goals

Production deployment for Cannab'IA must optimize for:

1. Patient data confidentiality
2. Tenant isolation integrity
3. Availability of webhook and dashboards
4. Traceability and incident response
5. Safe and repeatable releases

---

## 2) Environment Configuration

Key environment categories:

- Flask secrets/session settings
- MySQL connection
- WhatsApp verification/API settings
- Email SMTP settings
- Rate limit thresholds
- AI API key and model configs

Minimum production baseline:

- Unique strong `SECRET_KEY`
- TLS everywhere
- Production DB credentials (non-root, least privilege)
- Separate credentials per environment (dev/staging/prod)

---

## 3) Production Runtime Topology (Recommended)

```text
Internet
   |
   v
[Reverse Proxy / Load Balancer]
   |- TLS termination
   |- forwards X-Forwarded-* headers
   v
[WSGI/ASGI App Nodes]
   |- Flask app + SocketIO worker model
   |- shared session/rate-limit backend (recommended)
   v
[MySQL Primary/Replica]
   |- encrypted storage/backups
   v
[Log + Metrics + Alerting stack]
```

---

## 4) Flask and Proxy Security (`ProxyFix` Considerations)

When behind a reverse proxy, Flask may not trust forwarded protocol/IP headers unless configured.

Why this matters:

- Secure cookies may behave incorrectly if app thinks scheme is HTTP.
- Rate limit by IP can become inaccurate if proxy headers are mishandled.

Production best practice:

- use trusted proxy configuration (e.g., Werkzeug `ProxyFix`) with correct hop counts
- only trust headers from known internal proxy infrastructure

Misconfiguration risk:

- trusting arbitrary `X-Forwarded-For` enables IP spoofing in rate-limiting/audit logic.

---

## 5) Session and Cookie Hardening

Required production settings:

- `SESSION_COOKIE_SECURE = True` (HTTPS only)
- `SESSION_COOKIE_HTTPONLY = True`
- `SESSION_COOKIE_SAMESITE` set appropriately (`Lax` or stricter based on UX)
- session expiration and rotation policy

Current code forces `SESSION_COOKIE_SECURE=False` in app factory for local development convenience. Ensure production build overrides this safely.

---

## 6) CSRF Protection in Production

CSRF is already used in login/logout/scheduling forms.

Production checklist:

1. Keep all state-changing form actions CSRF-protected.
2. Ensure tokens rotate correctly across login/logout flows.
3. Add CSRF validation to any new POST/PUT/PATCH/DELETE form endpoint.
4. For JSON APIs, use alternate anti-CSRF/session strategy if browser-authenticated.

---

## 7) Rate Limiting Strategy

Current state:

- in-memory per-process buckets.

Production risk:

- multiple app instances do not share counters.

Recommended production pattern:

- central backend (Redis) for distributed counters
- separate policies for:
  - login endpoint
  - webhook endpoint
  - admin/AI endpoints

---

## 8) Database Production Hardening

1. Use dedicated DB user with least privileges.
2. Restrict inbound DB network access to app nodes.
3. Enable encrypted backups and tested restore procedure.
4. Track schema via migrations only (avoid runtime drift).
5. Monitor slow queries and add indexes based on observed access patterns.
6. Add tenant-aware constraints when multi-clinic mode is enabled.

---

## 9) Logging, Auditing, and Observability

Logging goals:

- correlate requests via `request_id`
- capture status and latency
- redact secrets/PII where possible

AI auditing goals:

- track success/failure rates
- track token and cost trends
- detect abnormal usage spikes

Operational recommendations:

- centralize logs (e.g., ELK/OpenSearch/Cloud logging)
- create alerts for:
  - high 5xx rates
  - repeated security-blocked AI attempts
  - sudden token/cost spikes
  - repeated login rate-limit hits

---

## 10) Secure Release Process

Release steps:

1. Run migrations in staging.
2. Validate login/session and CSRF flows.
3. Validate webhook path end-to-end with provider sandbox.
4. Validate role gates and tenant filter tests.
5. Validate AI pipeline and audit logging.
6. Deploy with health checks.
7. Observe logs/metrics post-release.

Rollback readiness:

- keep previous app image/artifact
- ensure backward-compatible migration strategy when possible
- define rollback procedure per release ticket

---

## 11) How to Add Features Without Breaking Tenant Isolation

Every new feature must pass this safety gate:

1. Is the data clinic-owned?
2. Does table include `clinic_id`?
3. Do all repository queries include `clinic_id` filter?
4. Is clinic membership verified before query execution?
5. Are aggregates filtered by clinic?
6. Are websocket payloads clinic-scoped?
7. Are tests covering cross-tenant non-visibility?

If any answer is “no”, feature is not production-safe for multi-clinic mode.

---

## 12) Cross-Tenant Leakage Test Checklist (Production Readiness)

- [ ] Tenant A user cannot view Tenant B rows by URL manipulation
- [ ] Tenant A user cannot modify Tenant B rows by ID guess
- [ ] Tenant A user cannot receive Tenant B websocket events
- [ ] Tenant A aggregate dashboards exclude Tenant B counts/costs
- [ ] AI audit pages enforce tenant filter and role policy

Run this checklist before every major release.

---

## 13) Incident Response Basics

If leakage is suspected:

1. Disable affected endpoint/feature flag immediately.
2. Capture timeframe and affected request IDs.
3. Query audit logs and access logs.
4. Identify root cause (missing filter, broken decorator, etc.).
5. Patch + add regression tests.
6. Revalidate all related endpoints.
7. Follow legal/compliance notification procedures.

---

## 14) Glossary

- **Hardening**: extra security controls applied for production safety.
- **Reverse proxy**: front server handling TLS/routing before app server.
- **ProxyFix**: Werkzeug middleware that adjusts request metadata from proxy headers.
- **Least privilege**: minimum required permissions only.
- **Regression test**: test ensuring a previous bug does not return.
