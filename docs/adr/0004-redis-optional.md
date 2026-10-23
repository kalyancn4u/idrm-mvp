# ADR-0004 — Redis Is an Optional Cache, Not a Dependency

**Status:** Accepted

## Context

The platform needs fast cross-process state (session lookups, rate-limit
counters, auto-approval caps). Redis is the standard answer, but adding a
hard dependency is a deployment cost.

## Decision

The platform runs **without Redis**. Every call through `shared/cache.py`
returns `None` on failure and the caller falls through to Postgres.

| Use case | With Redis | Without Redis |
|---|---|---|
| Session lookup | ~0.2 ms GET | ~1–3 ms indexed SELECT |
| Rate limit | Atomic INCR | Count from `rate_limit_events` |
| Auto-approval caps | Atomic Lua | Count from `auto_approval_decisions` |
| Policy cache | 60s TTL | SELECT each time |

The platform is **slower, never broken**.

## Consequences

- `REDIS_URL` may be empty. The app starts.
- `make test-no-redis` runs the full suite without Redis. If it fails,
  there is a hidden dependency somewhere.
- Redis runs with AOF (`--appendonly yes`), so counters survive a restart
  with at most 1 second of loss.
