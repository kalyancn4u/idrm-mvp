# ADR-0010 — All Sessions Are Server-Tracked

**Status:** Accepted

## Context

A stateless JWT can be verified without a database. But it cannot be revoked
— the only defence against a stolen token is its TTL, which is long.

## Decision

Every session has a row in `user_sessions`. The session id is a claim in
every access token (`sid`). Every request looks up the session.

- Fast path: Redis caches the lookup for 60s.
- Slow path: a single indexed `SELECT` joining `user_sessions` and `users`.
- Miss: 401.

Every session is revocable:

- **Single-device logout** — `POST /auth/logout`.
- **Password change** — bumps `token_version`, revokes all sessions.
- **Force logout** — same, from the dashboard.
- **Blacklist** — same, plus an entity-list entry.

## Consequences

- **One extra column on `users`:** `token_version`.
- **Six extra columns on `user_sessions`:** `refresh_token_hash`,
  `refresh_token_family`, `token_version_at_issue`, `last_activity_at`,
  `flagged_at`, `flag_reason`.
- **60-second revocation window** (worst case) when Redis caching is
  active.
- **Per-request cost:** ~0.2 ms (Redis) to ~3 ms (Postgres).
