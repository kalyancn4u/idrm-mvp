# Authentication and Sessions

> **Scope:** tokens, sessions, sign-in and sign-out.  
> **Owner of:** token lifetimes and the role list.  
> **See also:** [08-security.md](08-security.md) · [04-api-reference.md](04-api-reference.md)

## The two tokens

| Token | Lifetime | Purpose |
|---|---|---|
| Access | 30–120 min (+ jitter) | Every authenticated request |
| Refresh | 30–180 days (+ jitter, sliding) | Mint new access tokens |

## The claims

```json
{
  "sub": "8f4a…",
  "sid": "3e2b…",       ← session id — checked every request
  "ver": 4,             ← token version — checked every request
  "role": "citizen",
  "jti": "9a1c…",
  "typ": "access",
  "iat": 1728000000,
  "exp": 1728005400
}
```

## The field check on every request

```
1. Signature valid                 → 401
2. exp not passed                  → 401
3. typ == "access"                 → 401
4. Session lookup by sid (cache)   → miss = SELECT
5. session.revoked_at IS NULL      → 401 if revoked
6. session.expires_at > now()      → 401 if expired
7. idle timeout not exceeded       → 401
8. users.status == 'active'        → 401
9. claims.ver == users.token_version  → 401 (the blacklist)
```

## The frozen TTLs

| Role | Access TTL | Refresh TTL | Max sessions | Idle |
|---|---|---|---|---|
| citizen | 120 min ± 20 | 180 days ± 7 | 2 | 90 days |
| provider | 120 min ± 20 | 180 days ± 7 | 3 | 90 days |
| coordinator | 60 min ± 10 | 90 days ± 5 | 3 | 12 hours |
| admin | 30 min ± 5 | 30 days ± 3 | 2 | 4 hours |

## Why generous TTLs

Because **revocation is immediate** — the session + token version check
catches everything on the next request. Short TTLs were the old answer when
you had no revocation.

**Jitter spreads load.** Without it, 5,000 users who logged in at 9:00 AM
refresh at exactly the same minute. With ±20 min jitter and 120 min TTLs,
that load spreads across 40 minutes → ~0.04% CPU instead of a multi-second
spike.

## Refresh rotation

Every refresh issues a new token and replaces the stored hash, so the old
one no longer matches. If an old token is presented while the session is
still alive, the platform assumes theft and:

1. Revokes the entire token family
2. Bumps `users.token_version`
3. Writes an `auth.refresh_reuse_detected` audit row

A refresh on a session that is already revoked (logged out, or evicted by the
session limit) is simply refused with `session_revoked`.

## Concurrent session limits

Enforced at login: if you're at your limit, the oldest session is evicted
(marked revoked). This is what users expect from Google, Apple, and every
modern platform.

## Logout flows

| Scenario | What happens |
|---|---|
| Single-device logout | The session row is revoked |
| Password change | `token_version` bumps and all sessions are revoked, including the one used to change it. The new password may not repeat the current one or any of the previous five (`password_history`) |
| Admin force-logout | Same as above, from the dashboard |

## Client contract

```json
{
  "tokens": {
    "access_token": "…",
    "refresh_token": "…",
    "expires_in": 8432,
    "refresh_strategy": "on_demand",
    "jitter_applied": true
  }
}
```

- `on_demand` → don't set a timer; refresh only when a request returns
  401 `token_expired`.
- `jitter_applied` → don't treat `expires_in` as fixed.

## Without Redis

Everything still works. Session lookup goes from ~0.2 ms (Redis) to
~1–3 ms (Postgres indexed). Run `make test-no-redis` to prove it.

