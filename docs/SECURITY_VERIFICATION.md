# Security Verification

For each control IDRM claims, this document says how to *prove it*, not
just assert it. Run these in front of an auditor.

Every test is a copy-paste shell command.

---

## T1 — Password storage is not reversible

**Claim:** passwords are stored as bcrypt (cost 12) hashes, never plaintext.

**Verify:**

```bash
make psql
```

```sql
SELECT email, left(password_hash, 20) AS prefix
  FROM users
 LIMIT 5;
```

**Expected output:**

```
         email          |        prefix
------------------------+----------------------
 admin@idrm.local       | $2b$12$LQv3c1yqBWVHx
 coord.hyd@idrm.local   | $2b$12$LQv3c1yqBWVHx
 …
```

- The prefix `$2b$12$` = bcrypt with cost 12.
- There is no column anywhere that stores the plaintext.
- The full hash is unique per user (bcrypt salts each hash).

---

## T2 — Wrong password is rejected

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@idrm.local","password":"wrong"}' | jq
```

**Expected:**

```json
{
  "error": {
    "code": "invalid_credentials",
    "message": "The email or password is incorrect."
  }
}
```

Note: the message does not say *"wrong password"* — it is deliberately vague
to avoid disclosing whether the account exists.

---

## T3 — Access tokens expire

Wait for the TTL (or use a short TTL in a test env):

```bash
# In .env
JWT_ACCESS_TTL_CITIZEN_MIN=1
JWT_ACCESS_JITTER_CITIZEN_MIN=0
```

```bash
# Log in, get an access token
ACCESS=...
# Wait 2 minutes
sleep 120
curl -s -H "Authorization: Bearer $ACCESS" \
  http://localhost:8000/api/v1/users/me | jq
```

**Expected:**

```json
{
  "error": {
    "code": "token_expired",
    "message": "Access token has expired."
  }
}
```

---

## T4 — Refresh token cannot be used as an access token

```bash
# Get both tokens, then try the refresh token in the Authorization header
curl -s -H "Authorization: Bearer $REFRESH" \
  http://localhost:8000/api/v1/users/me | jq
```

**Expected:**

```json
{
  "error": {
    "code": "invalid_token",
    "message": "Access token is invalid."
  }
}
```

This is the **token type confusion** defence — the `typ` claim is checked.

---

## T5 — Blacklisted sessions are rejected on the next request

```bash
# 1. Log in and capture an access token
ACCESS=...

# 2. From the console, click "Force sign-out" for that user.

# 3. Use the access token again
curl -s -H "Authorization: Bearer $ACCESS" \
  http://localhost:8000/api/v1/users/me | jq
```

**Expected:**

```json
{
  "error": {
    "code": "token_version_mismatch",
    "message": "Token is stale."
  }
}
```

**This is the single most important test.** It proves that blacklisting
works even though the access token has not yet expired. The `token_version`
check catches what the TTL cannot.

---

## T6 — Refresh-token reuse triggers family revocation

```bash
# 1. Log in
TOKENS=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"priya.citizen@example.com","password":"IDRMseed#2026"}')
R1=$(echo $TOKENS | jq -r '.tokens.refresh_token')

# 2. Refresh once — get R2, R1 is now used
NEW=$(curl -s -X POST http://localhost:8000/api/v1/auth/refresh \
  -H 'Content-Type: application/json' -d "{\"refresh_token\":\"$R1\"}")
R2=$(echo $NEW | jq -r '.refresh_token')

# 3. Try to reuse R1 (the theft indicator)
curl -s -X POST http://localhost:8000/api/v1/auth/refresh \
  -H 'Content-Type: application/json' -d "{\"refresh_token\":\"$R1\"}" | jq
```

**Expected:**

```json
{
  "error": {
    "code": "invalid_token",
    "message": "Refresh token reuse detected."
  }
}
```

**Now prove the family was revoked** — try to use R2:

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/refresh \
  -H 'Content-Type: application/json' -d "{\"refresh_token\":\"$R2\"}" | jq
```

**Expected:**

```json
{
  "error": {
    "code": "invalid_token",
    "message": "Session has been revoked."
  }
}
```

The whole family is dead. This is what happens when a stolen refresh token
is used.

**Verify the audit event:**

```sql
SELECT created_at, action, severity
  FROM audit_logs
 WHERE action = 'auth.refresh_reuse_detected'
 ORDER BY created_at DESC
 LIMIT 1;
```

The severity is **critical**.

---

## T7 — The audit trail is append-only

```bash
make psql
```

```sql
-- Take a row id
SELECT id FROM audit_logs LIMIT 1;

-- Try to update it
UPDATE audit_logs SET action = 'tampered' WHERE id = '<the-id>';
```

**Expected:**

```
ERROR:  audit_logs is append-only — UPDATE and DELETE are forbidden
```

Try delete:

```sql
DELETE FROM audit_logs WHERE id = '<the-id>';
```

**Expected:**

```
ERROR:  audit_logs is append-only — UPDATE and DELETE are forbidden
```

The trigger blocks both. There is no application-level bypass.

---

## T8 — Cross-tenant access is rejected

```bash
# Log in as citizen A, get A's incident
A_ACCESS=...
INCIDENT_A=$(curl -s -H "Authorization: Bearer $A_ACCESS" \
  http://localhost:8000/api/v1/incidents/mine | jq -r '.data[0].id')

# Log in as citizen B
B_TOKENS=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"mohan.citizen@example.com","password":"IDRMseed#2026"}')
B_ACCESS=$(echo $B_TOKENS | jq -r '.tokens.access_token')

# Try to read A's incident
curl -s -H "Authorization: Bearer $B_ACCESS" \
  http://localhost:8000/api/v1/incidents/$INCIDENT_A | jq
```

**Expected:**

```json
{
  "error": {
    "code": "forbidden",
    "message": "You may not view this request."
  }
}
```

Ownership is checked in the service layer, not the route — so even a
crafted request cannot bypass it.

---

## T9 — CSRF is enforced on the dashboard

```bash
# Get the login page to obtain a session cookie
curl -s -c /tmp/cookies -b /tmp/cookies \
  http://localhost:5000/dashboard/login > /dev/null

# Try to POST without the CSRF token
curl -s -b /tmp/cookies -X POST \
  -d 'email=admin@idrm.local&password=Admin#2026' \
  -w '\n%{http_code}\n' \
  http://localhost:5000/dashboard/auth/login
```

**Expected:** `400` — the CSRF token is missing or invalid. The response
body will mention `CSRF`.

Every mutating form on the dashboard carries a hidden `csrf_token`.

---

## T10 — SQL injection is not possible

```bash
# Try to inject through a search field
curl -s "http://localhost:8000/api/v1/incidents?q=%27%20OR%201%3D1--" \
  -H "Authorization: Bearer $ACCESS" | jq
```

**Expected:** a normal list result (empty or filtered). No SQL error.
No unexpected rows. The `q` parameter is passed as a bound parameter to
SQLAlchemy — the `' OR 1=1--` string is treated as literal text.

---

## T11 — Rate limits are enforced

```bash
# Hammer the login endpoint
for i in $(seq 1 10); do
  curl -s -o /dev/null -w "%{http_code} " \
    -X POST http://localhost:8000/api/v1/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"email":"nobody@example.com","password":"wrong"}'
done
echo
```

**Expected:** the first 5 return `401`; the 6th onward return `429`.

```
401 401 401 401 401 429 429 429 429 429
```

The limit is 5 per minute per IP (or per bearer token if present).

---

## T12 — Security headers are present

```bash
curl -sI http://localhost:5000/dashboard/login | grep -iE '(x-frame|x-content|referrer|content-security)'
```

**Expected:**

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'; …
```

The CSP forbids `frame-ancestors` (clickjacking), restricts `script-src`
to `'self'` and a trusted CDN, and blocks inline event handlers.

---

## T13 — Exports are logged

```bash
# Download the incidents CSV
curl -s -b /tmp/cookies -o /tmp/incidents.csv \
  http://localhost:5000/dashboard/reports/export/incidents.csv

# Verify it appeared in the audit log
make psql
```

```sql
SELECT created_at, actor_id, action, new_values
  FROM audit_logs
 WHERE action = 'dashboard.export.incidents_csv'
 ORDER BY created_at DESC
 LIMIT 1;
```

**Expected:** one row showing the actor, the row count exported, and the
timestamp.

If someone exfiltrates the incidents list, this is how you know.

---

## The one-page summary table

| # | Control | Test | Result |
|---|---|---|---|
| T1 | bcrypt cost 12 | `SELECT left(password_hash, 7)` | `$2b$12$` |
| T2 | Wrong password rejected | Login with wrong password | 401 |
| T3 | Access tokens expire | Wait for TTL, retry | 401 token_expired |
| T4 | Token type confusion rejected | Use refresh as access | 401 invalid_token |
| T5 | Blacklist is immediate | Force logout, reuse token | 401 token_version_mismatch |
| T6 | Reuse detection works | Reuse a used refresh token | 401 invalid_token |
| T7 | Audit is append-only | UPDATE audit_logs | ERROR |
| T8 | Cross-tenant access denied | Read another citizen's incident | 403 |
| T9 | CSRF enforced | POST without token | 400 |
| T10 | SQL injection impossible | Inject in `q` | Normal result |
| T11 | Rate limits enforced | Hammer login | 429 after 5 |
| T12 | Security headers present | `curl -I` | Headers present |
| T13 | Exports logged | Download CSV | Audit row appears |

**Run all 13 in under 10 minutes.** Every claim is testable.

---

## Reporting a security issue

Do not open a public issue. Email the maintainers directly. Include:

- A description of the issue
- Steps to reproduce
- Potential impact
- Any suggested fix

We will acknowledge within 48 hours.
