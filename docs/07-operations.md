# Operations Runbook

## Deployment

### Development

```bash
make setup
make run          # API :8000, Dashboard :5000
```

### Production (reference)

```bash
# 1. Build
docker build -t idrm:0.1.0 .

# 2. Configure
cp .env.example .env
$EDITOR .env      # APP_ENV=production, DASHBOARD_SECRET_KEY, DASHBOARD_SESSION_COOKIE_SECURE=1,
                  # DATABASE_URL + DATABASE_URL_SYNC, S3_SECRET_KEY, ADMIN_INITIAL_PASSWORD
# With APP_ENV=production both apps REFUSE TO START while any of those is
# still a development default — the error names the setting.

# 2b. JWT keys — the image contains none; create them on the host
python scripts/generate_keys.py        # writes ./keys/ (kept if they exist)

# 2c. Schema + reference data
alembic upgrade head                   # needs ADMIN_INITIAL_PASSWORD (12+ chars)
python -m scripts.seed --reference-only   # regions only; NEVER the demo seed

# 3. Run BOTH apps
docker run -d --name idrm-api \
  --env-file .env -p 8000:8000 -v "$PWD/keys:/app/keys:ro" \
  --restart unless-stopped idrm:0.1.0

docker run -d --name idrm-dashboard \
  --env-file .env -p 5000:5000 --restart unless-stopped \
  idrm:0.1.0 gunicorn -w 4 -b 0.0.0.0:5000 "dashboard:create_dashboard()"
```

## Monitoring

**Health endpoint:**
```bash
curl -fsS https://idrm.example.com/api/v1/health | jq
```

**Metrics worth alerting on:**

| Metric | Warning | Critical |
|---|---|---|
| Open incidents | > 100 | > 200 |
| Critical incidents | > 5 | > 10 |
| Overdue verifications | > 20 | > 50 |
| DB connection pool saturation | > 80% | > 95% |

## Scheduled jobs

| Job | Frequency | Command |
|---|---|---|
| Purge expired sessions | daily | `DELETE FROM user_sessions WHERE expires_at < now() - INTERVAL '90 days'` |
| Purge old login attempts | daily | `DELETE FROM login_attempts WHERE occurred_at < now() - INTERVAL '90 days'` |
| `VACUUM ANALYZE` | nightly | `VACUUM ANALYZE;` |
| Backup | nightly | `make dump` |

## Backup and restore

### Logical dump
```bash
make dump
# → backups/idrm_YYYYMMDD_HHMMSS.sql
```

### Restore
```bash
psql -h $PGHOST -U $PGUSER -d idrm_db -f backups/idrm_20260115_020001.sql
```

### Verify
```sql
SELECT count(*) FROM users;
SELECT count(*) FROM incidents WHERE status IN ('created','approved','accepted','in_progress');
SELECT count(*) FROM audit_logs;
```

## RPO / RTO

| Method | RPO | RTO |
|---|---|---|
| Logical dump | 24 hours | 30–60 min |
| WAL archiving (pgBackRest) | 5 min | 30 min |

For production: use WAL archiving.

## Incident playbook

### "The dashboard is slow"

```sql
SELECT pid, now() - query_start AS duration, query
  FROM pg_stat_activity
 WHERE state = 'active' AND query NOT ILIKE '%pg_stat_activity%'
 ORDER BY duration DESC;

SELECT relname, seq_scan, idx_scan
  FROM pg_stat_user_tables
 WHERE seq_scan > idx_scan AND seq_scan > 1000
 ORDER BY seq_scan DESC;
```

### "Requests stopped being auto-approved"

Auto-approval runs when an incident is created. If it stops:

1. Check `/dashboard/policies` — is the policy still active, and has its
   `effective_to` end time passed? (Expired policies stop on their own.)
2. Check `/dashboard/policies/decisions` — are recent decisions `matched_policy`?
3. Check `AUTO_APPROVAL_ENABLED` env var.

### "The audit trail has a gap"

1. Check whether the app crashed during a write.
2. Confirm the immutability trigger still exists:
   ```sql
   SELECT tgname FROM pg_trigger WHERE tgname = 'trg_audit_immutable';
   ```
   Expect one row.

### "Users cannot log in"

```sql
SELECT email, role, status, failed_login_attempts, locked_until FROM users;
-- locked_until in the future = five wrong passwords; wait 15 minutes or:
UPDATE users SET locked_until = NULL, failed_login_attempts = 0 WHERE email = '...';

SELECT email, left(password_hash, 7) FROM users;
-- expect '$2b$12$' (bcrypt, cost 12)
```

Also check the JWT keys exist where `JWT_PRIVATE_KEY_PATH` points — without
them the API cannot issue a token.

## Upgrade procedure

```bash
# 1. Back up
make dump

# 2. Pull
git pull

# 3. Update dependencies
make install

# 4. Apply migrations (idempotent)
make migrate

# 5. Test
make test

# 6. Restart both apps
systemctl restart idrm-api idrm-dashboard

# 7. Verify
curl -fsS https://idrm.example.com/api/v1/health | jq
```

## Scaling

| Symptom | Fix |
|---|---|
| High CPU on the app tier | Add gunicorn workers |
| Slow dashboards | Add a materialized view for KPIs |
| Slow audit browsing | Partition `audit_logs` by month |
| Slow identity search | Confirm trigram indexes are used (`EXPLAIN ANALYZE`) |
| Connection pool exhaustion | Raise `pool_size` / `max_overflow` in `shared/db.py` (they are fixed in code, not env vars), or add PgBouncer |
| Large audit table | Archive > 2 years to cold storage |

## Security operations

| Task | Frequency | Command |
|---|---|---|
| Rotate `DASHBOARD_SECRET_KEY` | quarterly | update `.env`, restart (signs everyone out of the console) |
| Rotate JWT keypair | quarterly | `python scripts/generate_keys.py --force`, restart (signs every API user out) |
| Rotate DB password | quarterly | `ALTER ROLE idrm_user PASSWORD '...'` |
| Review admin accounts | monthly | `SELECT * FROM users WHERE role='admin';` |
| Verify audit immutability | monthly | `UPDATE audit_logs SET action='x'; -- expect an error` |
| Review entity lists | monthly | `/dashboard/policies/entity-lists` |
