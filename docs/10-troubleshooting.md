# Troubleshooting & FAQ

> **Scope:** common failures and how to fix them.  
> **Owner of:** the list of known symptoms and their fixes.  
> **See also:** [01-getting-started.md](01-getting-started.md) · [07-operations.md](07-operations.md)

## Installation

### `make infra-up` fails — "Cannot connect to the Docker daemon"

Start Docker, or use a native Postgres:

```bash
sudo -u postgres psql -c "CREATE ROLE idrm_user LOGIN PASSWORD 'idrm_pass';"
sudo -u postgres psql -c "CREATE DATABASE idrm_db OWNER idrm_user;"
sudo -u postgres psql -d idrm_db -c "CREATE EXTENSION postgis;"
make migrate seed
```

### `psycopg2.OperationalError: could not connect`

```bash
pg_isready -h localhost -p 5432
psql -h localhost -U idrm_user -d idrm_db -c 'SELECT 1;'
grep DATABASE_URL .env
```

### `ModuleNotFoundError: No module named 'flask'`

```bash
make install
.venv/bin/python -c "import flask; print(flask.__version__)"
```

## Database

### `relation "..." does not exist`

Migrations have not been applied to this database. Run `make migrate`
(`make db-reset` rebuilds a development database from scratch).

### `UPDATE audit_logs` fails

That is the immutability trigger working:

```
ERROR: audit_logs is append-only — UPDATE and DELETE are forbidden
```

The table owner can still remove the guard (this is why production should
run the app as a non-owner role — see [Security](08-security.md)):

```sql
DROP TRIGGER trg_audit_immutable ON audit_logs;
-- ... your change ...
CREATE TRIGGER trg_audit_immutable BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION block_audit_mutation();
```

Do not do this in production.

### Auto-approval not firing

1. Check `AUTO_APPROVAL_ENABLED=1` in `.env`.
2. Check `/dashboard/policies` — is the policy active, and still inside its
   `effective_from` … `effective_to` period?
3. Check `/dashboard/policies/decisions` — is there a recent decision?
4. Check the incident's region — is it inside the policy's region scope?
5. Check the daily cap in Redis: `redis-cli keys 'idrm:cap:*'`.
6. Does the policy use a condition the engine does not enforce (for example
   `time_of_day_start`)? Such a policy never matches; the API log says so.

### Seeded users can't log in

1. Did the seed finish? It prints `✔ Seed complete`.
   ```bash
   make seed
   ```
2. Is the account locked after five wrong passwords?
   ```sql
   SELECT email, status, locked_until, left(password_hash, 7) FROM users;
   -- expect '$2b$12$' and locked_until empty or in the past
   ```
3. `admin@idrm.local` is created by migration `0003`, with
   `ADMIN_INITIAL_PASSWORD` if that was set, otherwise the demo password.

## Application

### Login redirects back to login

Cookie settings. In production behind a proxy:

```dotenv
DASHBOARD_SESSION_COOKIE_SECURE=1   # the browser must reach the console over HTTPS
TRUST_FORWARDED_FOR=1               # only behind a proxy you control
```

`TRUST_FORWARDED_FOR=1` turns on Werkzeug's `ProxyFix`, so the console knows
the original request was HTTPS. A secure cookie over plain HTTP is never sent
back, which shows up as exactly this loop.

### Sent back to the login page after logging in

Only `coordinator` and `admin` may use the console, and the check is repeated
on every request. If an account is suspended or its role is changed, the next
click signs it out.

```sql
SELECT email, role, status FROM users WHERE email = '...';
```

### 401 on API with a valid token

The message says which check failed:

| Response | Meaning |
|---|---|
| `token_expired` | The `exp` claim is past |
| `session_not_found` | The `sid` claim points to no session |
| `session_revoked` | Someone logged you out |
| `token_version_mismatch` | Password was changed, an admin forced a sign-out, or a stolen refresh token was detected — re-login |
| `account_disabled` | Your account was disabled |

### Rate limited (429)

Limits are counted per client address (and, for login, per email). Wait for
the window to pass. Behind a proxy, set `TRUST_FORWARDED_FOR=1` or every user
shares the proxy's address and one limit.

### Styles look broken / unstyled

```bash
ls dashboard/static/css/design-system.css
curl -I http://localhost:5000/dashboard/static/css/design-system.css
```

Check the browser console for CSP errors.

## Performance

### The incidents list takes 5+ seconds

```sql
ANALYZE incidents;
EXPLAIN ANALYZE
SELECT * FROM incidents
 WHERE status IN ('created','approved','accepted','in_progress')
 ORDER BY created_at DESC LIMIT 25;
```

Look for `Seq Scan`. If present, force an index-only scan or reindex:

```sql
REINDEX INDEX ix_incidents_status_created;
```

### The audit trail is slow to browse

After 10⁷ rows, partition `audit_logs` by month. See the ops runbook.

## FAQ

**Q: Why two apps instead of one with a role toggle?**
A: Because the public API's audience is untrusted, and the staff console's is
semi-trusted. The separation is structural, not cosmetic.

**Q: Why not delete revoked sessions?**
A: History. "Who was logged in when the incident started?" is answerable only
if the row survives. Sessions are retained for 90 days post-expiry.

**Q: Why is the audit table not in a separate database?**
A: Because the audit row must be written in the same transaction as the
change. A separate DB means either 2PC or eventual consistency — neither is
acceptable for an audit trail.

**Q: Can I use MySQL?**
A: Not without changes. The immutability trigger, PostGIS geometry, `INET`
type, and `JSONB` are PostgreSQL-specific.

**Q: How do I add an auto-approval policy?**
A: `POST /api/v1/policies` (see [Governance](12-governance.md)). The console
can switch an existing policy on or off but has no form to create one.

**Q: How do I add an entity to the blocklist?**
A: `/dashboard/policies/entity-lists` — one form. Today only `email` entries
are enforced, when a help request is created.

**Q: Where are the passwords?**
A: In `.env` for the DB; bcrypt hashes in `users.password_hash`. The demo
password is documented in the README and is for development only.

**Q: Can I run this without Docker?**
A: Yes. Install PostgreSQL+PostGIS natively. Everything else works.

**Q: Can I run without Redis?**
A: Yes. `make test-no-redis` proves it. Slower, never broken.

**Q: What is `token_version`?**
A: An integer on `users`. When it changes, every JWT issued before the change
is rejected on the next request. It is how password changes and force-logouts
take effect immediately.
