# Security & IAM

## Threat model

| # | Threat | Impact | Control |
|---|---|---|---|
| T1 | Unauthorized console access | Full compromise | Flask-Login, bcrypt (cost 12), role gate |
| T2 | Privilege escalation | Citizen → staff | Sign-up limited to `citizen`/`provider`; `@roles_required`; `ALLOWED_DASHBOARD_ROLES`; ownership checks (`app/core/authz.py`) |
| T3 | CSRF | Attacker triggers a state change | CSRF on every dashboard POST form |
| T4 | XSS | Session theft | Jinja2 autoescape; strict CSP |
| T5 | SQL injection | DB compromise | SQLAlchemy parameter binding |
| T6 | Audit tampering | Loss of non-repudiation | PG trigger blocks UPDATE/DELETE |
| T7 | Repudiation | "I didn't do that" | Actor id, IP and request id on every audited write |
| T8 | Session hijack | Account takeover | HttpOnly, SameSite=Lax, Secure in prod |
| T9 | Clickjacking | UI redressing | `X-Frame-Options: DENY`, CSP `frame-ancestors 'none'` |
| T10 | Data exfiltration via export | Bulk loss | Every export audit-logged |
| T11 | Insider quietly changing a request's state | Controls bypassed | One shared state machine (`shared/lifecycle.py`); every transition writes an `incident_updates` row and an audit row |
| T12 | Credential stuffing | Account takeover | 5 wrong passwords lock the account 15 min (API and console); rate limit per address and per email |

## Authentication

### Password storage

```python
bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12))   # shared/security.py
```

bcrypt, cost 12. Hashes start with `$2b$12$`.

### Session

| Setting | Value |
|---|---|
| Cookie | `SESSION_COOKIE_HTTPONLY=True` |
| SameSite | `Lax` |
| Secure | True in prod |
| Session lifetime | 8 hours |
| `session_protection` | `strong` |

## The two-token JWT

See [Auth & Sessions](13-auth-and-sessions.md) for the full design.

**The key security property:** every request checks `sid` (session alive)
and `ver` (token current). Blacklist → bump `token_version` → all tokens
invalidated on the next request.

## Authorization matrix

### FastAPI roles

| Permission | citizen | provider | coordinator | admin |
|---|:-:|:-:|:-:|:-:|
| view own incidents | ✅ | ✅ | ✅ | ✅ |
| create incident | ✅ | ❌ | ✅ | ✅ |
| accept/start/complete | ❌ | ✅ | ❌ | ❌ |
| approve/reject | ❌ | ❌ | ✅ | ✅ |
| view all incidents | ❌ | ✅ | ✅ | ✅ |
| create a region-scoped, time-limited incident policy | ❌ | ❌ | ✅ | ✅ |
| create any other policy | ❌ | ❌ | ❌ | ✅ |

### Dashboard roles

Every console route is guarded by a named permission from the table in
`dashboard/security.py` (`view.*` to see a page, `act.*` to change something,
`export.data` for the CSV). That table is the single place to change who may
do what.

| Permission | coordinator | admin |
|---|:-:|:-:|
| View overview | ✅ | ✅ |
| Use Dispatch Console | ✅ | ✅ |
| Approve/reject incidents | ✅ | ✅ |
| Verify organizations | ✅ | ✅ |
| Issue alerts | ✅ | ✅ |
| Change user role | ❌ | ✅ |
| Change user status | ❌ | ✅ |
| Force sign-out user | ❌ | ✅ |
| Create auto-approval policies | ❌ | ✅ |

## Defence in depth

1. **Route decorator** — `@roles_required(…)`, `@permission_required(…)`
2. **Template guard** — `{% if current_user.role == 'admin' %}`
3. **Database role** — grant the app's DB user only the privileges it needs
4. **Audit** — every state change is a row

Layers 1–2 are authoritative. 3 is the backstop.

## The audit trail as a control

| Property | How |
|---|---|
| Completeness | Every writer calls `audit.log_*` |
| Accuracy | Full `old_values` / `new_values` JSONB snapshots |
| Attribution | `actor_id` + `ip_address` |
| Immutability | `BEFORE UPDATE OR DELETE` trigger raises (see the limits below) |
| Timeliness | Same transaction as the change |
| Availability | Standard table; index-only reads |

### Proving immutability

```sql
UPDATE audit_logs SET action = 'tampered' WHERE id = (SELECT id FROM audit_logs LIMIT 1);
-- ERROR: audit_logs is append-only — UPDATE and DELETE are forbidden
```

Run this in front of an auditor. It settles the question in 5 seconds.

### What the trigger does not stop

Be precise about the claim. The trigger stops `UPDATE` and `DELETE`, from the
application and from `psql`. It does **not** stop:

- `TRUNCATE` — left possible on purpose for development (ADR-0002);
- a database role that **owns** the table dropping the trigger. In the
  default setup the application connects as the owner.

For real tamper-resistance run the application as a role that has only
`INSERT` and `SELECT` on `audit_logs`, and keep the owner role for migrations.

## Control mapping

### ISO 27001:2022

| Control | Implementation |
|---|---|
| A.5.15 Access control | `auto_approval_policies`, `entity_lists` |
| A.5.16 Identity management | `users`, `personnel_statuses` |
| A.5.17 Authentication information | `password_hash`, `login_attempts` |
| A.5.18 Access rights | `users.role`, `organization_members`, `volunteer_enrollments` |
| A.8.2 Privileged access | `role` field, dashboard gate |
| A.8.5 Secure authentication | bcrypt cost 12, JWT RS256 |
| A.8.15 Logging | `audit_logs` |
| A.8.16 Monitoring | Dispatch console, BigBoard |

### SOX ITGC

| Control | Implementation |
|---|---|
| Access provisioning | `organization_members`, `volunteer_enrollments` |
| Access removal | Session revocation, token version bump |
| Privileged access review | Dashboard role changes are audited |
| Change log | `audit_logs` with before/after snapshots |

## Hardening checklist

| Item | Status |
|---|---|
| `DASHBOARD_SECRET_KEY` is random and ≥ 32 bytes | ⬜ operator (start-up fails in production if it is the default) |
| `DASHBOARD_SESSION_COOKIE_SECURE=1` | ⬜ operator (start-up fails in production if it is off) |
| `ADMIN_INITIAL_PASSWORD` set before the first migration | ⬜ operator (migration refuses in production without it) |
| `TRUST_FORWARDED_FOR=1` only behind your own proxy | ⬜ operator |
| TLS terminated in front of the app | ⬜ operator |
| Database not exposed to the internet | ⬜ operator |
| Least-privilege DB role | ⬜ operator — the default setup runs the app as the table owner |
| No secrets in the repo | ✅ `.gitignore` |
| CSRF on all mutating routes | ✅ Flask-WTF |
| Security headers set | ✅ CSP, X-Frame-Options, Referrer-Policy |
| Parameterised queries only | ✅ SQLAlchemy |
| Audit immutability | ✅ PG trigger |
| Dependency pinning | ✅ `requirements.txt` |
| Login failures logged | ✅ |
| Export logging | ✅ |
