# ADR-0013 — Two-Token JWT with Server-Side Session Verification

**Status:** Accepted

## Context

We need stateless-fast auth **and** immediate revocation. Pure JWT cannot
revoke. Pure server-side sessions lose the speed.

## Decision

1. **Two tokens.** Access (short, jittered) + refresh (long, jittered, sliding).
2. **The `sid` claim** is checked every request against `user_sessions`.
3. **The `ver` claim** is checked every request against `users.token_version`.
   Password change / force-logout / blacklist bumps the version.
4. **Refresh rotation with family-based reuse detection.** If a used refresh
   token appears again, the whole family is revoked and the version is bumped.
5. **Cache-first.** Redis caches the session lookup with a 60s TTL; Postgres
   is the fallback.
6. **Concurrent-session limits.** Enforced at login by evicting the oldest.
7. **All TTLs are jittered** (±5–20 min access, ±3–7 days refresh).

## Consequences

- **One new column on `users`:** `token_version`.
- **New columns on `user_sessions`:** `refresh_token_hash`,
  `refresh_token_family`, `token_version_at_issue`, `last_activity_at`,
  `flagged_at`, `flag_reason`.
- **60s revocation window** (worst case) when Redis caching is active.
- **Smooth CPU profile** instead of a thundering-herd spike at token expiry.

