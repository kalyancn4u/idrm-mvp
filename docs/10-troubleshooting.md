# Troubleshooting & FAQ

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

### `relation "audit_event" does not exist`

You ran migrations out of order. `make db-reset` rebuilds correctly.

### `UPDATE audit_logs` fails

That is the immutability trigger working:

```
ERROR: audit_logs is append-only — UPDATE and DELETE are forbidden
```

To modify audit rows, drop the trigger:

```sql
DROP TRIGGER trg_audit_immutable ON audit_logs;
-- ... your change ...
CREATE TRIGGER trg_audit_immutable BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION block_audit_mutation();
```

Do not do this in production.

### Auto-approval not firing

1. Check `AUTO_APPROVAL_ENABLED=1` in `.env`.
2. Check `/dashboard/policies` — is the policy active?
3. Check `/dashboard/decisions` — is there a recent decision?
4. Check the incident's region — is it inside the policy's region scope?
5. Check the daily cap in Redis: `redis-cli keys 'idrm:cap:*'`.

### Seeded users can't log in

Password hash is `PLACEHOLDER`:

```bash
make seed
```

Verify:

```sql
SELECT username, left(password_hash, 12) FROM users;
-- expect 'pbkdf2:sha256' not 'PLACEHOLDER'
```

## Application

### Login redirects back to login

Cookie settings. In production behind a proxy:

```dotenv
SESSION_COOKIE_SECURE=0    # behind a TLS proxy
```

Add `ProxyFix`:

```python
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
```

### 403 on every page after logging in

Check the role:

```sql
SELECT username, role FROM users WHERE username = 'auditor';
```

An auditor cannot access `/dashboard/*`. That is the design.

### 401 on API with a valid token

The message says which check failed:

| Response | Meaning |
|---|---|
| `token_expired` | The `exp` claim is past |
| `session_not_found` | The `sid` claim points to no session |
| `session_revoked` | Someone logged you out |
| `token_version_mismatch` | Password was changed — re-login |
| `account_disabled` | Your account was disabled |

### Rate limited (429)

The token bucket refills per window. Wait 60 seconds or use a different
identity.

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
A: Insert a row into `auto_approval_policies`, or use the dashboard. No code
change required.

**Q: How do I add an entity to the blocklist?**
A: `/dashboard/policies/entity-lists` — one form. The engine enforces it on
the next request.

**Q: Where are the passwords?**
A: In `.env` for the DB; PBKDF2 hashes in `users.password_hash`. The demo
password is documented in the README and is for development only.

**Q: Can I run this without Docker?**
A: Yes. Install PostgreSQL+PostGIS natively. Everything else works.

**Q: Can I run without Redis?**
A: Yes. `make test-no-redis` proves it. Slower, never broken.

**Q: What is `token_version`?**
A: An integer on `users`. When it changes, every JWT issued before the change
is rejected on the next request. It is how password changes and force-logouts
take effect immediately.
