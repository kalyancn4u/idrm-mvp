# Deployment Checklist

A production readiness checklist. Every box must be checked before going
live. Print this, tick the boxes, keep it.

---

## 1. Secrets and keys

- [ ] **`SECRET_KEY` is set and random.**
      ```bash
      openssl rand -hex 32
      # → paste into .env as SECRET_KEY
      ```

- [ ] **JWT keypair is generated and stored outside the repo.**
      ```bash
      make keys
      # keys/ is .gitignore'd
      # In production, mount these from a secret store
      ```

- [ ] **`DASHBOARD_SECRET_KEY` is set and different from `SECRET_KEY`.**
      Generate separately. Never reuse.

- [ ] **Database password is strong.** Not `idrm_pass`.
      ```sql
      ALTER ROLE idrm_user PASSWORD '<new-strong-password>';
      ```

- [ ] **MinIO credentials are changed from defaults.** Not `minioadmin`.

- [ ] **No secrets in `.env.example`.** It ships to the repo. Verify.

---

## 2. Environment

- [ ] **`APP_ENV=production`.** Enables the production config guard.

- [ ] **`SESSION_COOKIE_SECURE=1`.** Requires HTTPS.

- [ ] **`DASHBOARD_SESSION_COOKIE_SECURE=1`.** Same.

- [ ] **`ALLOWED_ORIGINS`** contains only production URLs.

- [ ] **`DATABASE_URL`** uses a non-superuser role.

- [ ] **`REDIS_URL`** is set (recommended for production).
      If omitted, the platform runs but is slower.

- [ ] **`AUTO_APPROVAL_ENABLED`** is `1` (or `0` if you want it off initially).

- [ ] **Upload limits are appropriate for your storage.**

---

## 3. Database

- [ ] **PostgreSQL 16 with PostGIS 3.4+** is installed.

- [ ] **Extensions are present:**
      ```sql
      \dx
      -- Expect: postgis, pgcrypto, pg_trgm, unaccent
      ```

- [ ] **Migrations applied:**
      ```bash
      make migrate
      alembic current   # expect "0003_seed_admin (head)"
      ```

- [ ] **Reference data seeded:**
      ```bash
      make seed
      ```

- [ ] **Connection pool sized correctly** for your workload.
      Default: `pool_size=10, max_overflow=20`.

- [ ] **Backups configured.** Cron `make dump` at minimum.

- [ ] **Backup restore has been drilled.** Not just configured.

- [ ] **`VACUUM ANALYZE` scheduled nightly.**

- [ ] **The audit table's immutability trigger is present:**
      ```sql
      SELECT tgname FROM pg_trigger WHERE tgname = 'trg_audit_immutable';
      -- Expect one row
      ```

---

## 4. Application

- [ ] **Docker image builds.**
      ```bash
      docker build -t idrm:0.1.0 .
      ```

- [ ] **Both apps start successfully.**
      ```bash
      docker run -p 8000:8000 --env-file .env idrm:0.1.0 &
      docker run -p 5000:5000 --env-file .env idrm:0.1.0 \
          gunicorn -w 4 -b 0.0.0.0:5000 "dashboard:create_dashboard()" &
      ```

- [ ] **Health endpoint responds.**
      ```bash
      curl -fsS https://api.example.com/api/v1/health
      # → {"status":"ok","components":{"database":{"ok":true}}}
      ```

- [ ] **Test suite passes.**
      ```bash
      make test
      make test-no-redis
      ```

- [ ] **Boundary check passes.**
      ```bash
      make lint
      ```

---

## 5. TLS and proxy

- [ ] **TLS is terminated in front of both apps.** No plain HTTP.

- [ ] **Certificate is valid and auto-renewing.**

- [ ] **Reverse proxy sets the right headers:**
      ```
      X-Forwarded-For
      X-Forwarded-Proto
      X-Real-IP
      ```

- [ ] **`ProxyFix` is enabled** if behind a proxy:
      ```python
      from werkzeug.middleware.proxy_fix import ProxyFix
      app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
      ```

- [ ] **HTTP redirects to HTTPS** at the load balancer.

- [ ] **HTTP/2 is enabled** if the load balancer supports it.

---

## 6. Network isolation

- [ ] **PostgreSQL is not exposed to the public internet.**
      Bind to `127.0.0.1` or an internal network only.

- [ ] **MinIO console is not public.** Internal only.

- [ ] **Redis is not public.** Internal only.

- [ ] **The dashboard is behind VPN or internal-only LB.**
      It is a staff tool; it has no reason to be public.

- [ ] **The API is public** (it needs to be — citizens use it).

- [ ] **Firewall rules** restrict traffic between tiers.

---

## 7. Monitoring

- [ ] **Logs are collected.** `logs/idrm.log` or stdout → log aggregator.

- [ ] **Log rotation is configured.** The app rotates at 5 MB × 5 backups.

- [ ] **Health endpoint is polled** by your monitor.

- [ ] **Alerts are configured:**
      - `/api/v1/health` returns non-200 for > 2 minutes
      - Error rate > 1%
      - Latency p95 > 1 second
      - Database connection pool saturation > 80%

- [ ] **Dashboards exist** for the above.

- [ ] **On-call rotation** is established.

---

## 8. Backups

- [ ] **Backups are automated.** Nightly at minimum.

- [ ] **Backups are stored off-host.** Different physical location.

- [ ] **Backups are encrypted at rest.**

- [ ] **Retention policy is defined.** 30 days? 90? 1 year?

- [ ] **Restore has been tested** on a clean host.

- [ ] **RPO is documented.** What is the acceptable data loss window?

- [ ] **RTO is documented.** How long to restore service?

- [ ] **For WAL archiving (recommended):** `pgBackRest` or `WAL-G` configured.

---

## 9. Security headers

Verify:

```bash
curl -sI https://api.example.com/health
```

Should include:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'; …
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

- [ ] **All headers present.**

- [ ] **`Strict-Transport-Security`** is added at the load balancer:
      ```
      Strict-Transport-Security: max-age=31536000; includeSubDomains
      ```

- [ ] **Run [SECURITY_VERIFICATION.md](SECURITY_VERIFICATION.md) end-to-end.**
      All 13 tests pass.

---

## 10. Operations

- [ ] **The operations runbook** (`docs/07-operations.md`) is printed
      and in the on-call binder.

- [ ] **The troubleshooting guide** (`docs/10-troubleshooting.md`) is
      available to the on-call engineer.

- [ ] **Incident response plan** exists.

- [ ] **Escalation path** is defined.

- [ ] **Post-mortem template** is ready.

---

## 11. Compliance

- [ ] **Data residency** is documented. Where does the data physically live?

- [ ] **PII inventory** exists. What PII does the platform store?
      (Names, emails, phones, IPs, locations.)

- [ ] **Retention policy** exists. How long is data kept?

- [ ] **Deletion policy** exists. Can a user request deletion? How is it
      handled given the append-only audit?

- [ ] **Access controls** are documented per role.

- [ ] **Audit retention** is defined. The audit table must not be purged.

---

## 12. Go-live

- [ ] **All above boxes are ticked.**

- [ ] **A dry-run deployment has happened** on staging.

- [ ] **A smoke test** has run against staging.
      ```bash
      BASE_URL=https://staging.example.com make smoke
      ```

- [ ] **Rollback procedure** is written and tested.

- [ ] **The team knows** the go-live window.

- [ ] **Someone is on-call** for the first 24 hours.

- [ ] **A post-go-live check** is scheduled at +24 h and +7 d.

---

## 13. First-week watch list

In the first week, watch for:

- [ ] Error rate
- [ ] Latency (p50, p95, p99)
- [ ] Database connection count
- [ ] Redis hit rate (if Redis is used)
- [ ] Disk usage (audit table grows)
- [ ] Failed login rate (sign of brute force)
- [ ] Rate-limit events (sign of abuse)
- [ ] Auto-approval decision rate (is it firing?)
- [ ] Backup success
- [ ] Certificate expiry

---

## When something is not right

| Symptom | Where to look |
|---|---|
| 500 errors spike | `logs/idrm.log` |
| Slow | `pg_stat_activity` for long queries |
| Audit growing fast | Disk usage; consider partitioning |
| Redis unavailable | The platform still works; check the cache warning |
| Backup failed | Disk space? Credentials? Network? |

---

## The five-minute sanity check

After go-live, run:

```bash
# 1. Health
curl -fsS https://api.example.com/api/v1/health

# 2. Log in
curl -s -X POST https://api.example.com/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@idrm.local","password":"<prod-password>"}' | jq

# 3. Create an incident
curl -s -X POST https://api.example.com/api/v1/incidents \
  -H 'Content-Type: application/json' \
  -d '{"service_type":"water","priority":"low","description":"Production smoke test.","location":{"latitude":17.4,"longitude":78.48}}' | jq

# 4. Open the console in a browser and verify the incident appears

# 5. Check the audit trail for the smoke test
```

If all five pass, the deployment is healthy.

---

## Sign-off

| Role | Name | Date |
|---|---|---|
| Deployer | __________ | __________ |
| Reviewer | __________ | __________ |
| On-call | __________ | __________ |
