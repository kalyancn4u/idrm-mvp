# ADR-0007 — Auto-Approval Is Policy-Driven and Synchronous

**Status:** Accepted

## Context

Manual coordinator approval was a bottleneck during large-scale disasters.
A rule-based auto-approval mechanism was needed for low-risk cases, with
caps, audit, and reversibility.

## Decision

1. Auto-approval is **policy-driven**. Policies are rows in
   `auto_approval_policies`, validated by Pydantic on load and write.
2. One engine (`shared/governance/evaluator.py`) serves both incident
   approval and provider verification, discriminated by `applies_to`.
3. Evaluation is **synchronous**, in the same request as creation.
4. Counters live in **Redis** (atomic, cross-process), with the durable
   decision log in Postgres.
5. Regions are **PostGIS polygons** in a `regions` table; region is
   derived from GPS coordinates via `ST_Covers`.
6. A single env var `AUTO_APPROVAL_ENABLED` is the kill switch.
7. **Never fail-open.** Any evaluation error results in `deferred`.

## Consequences

- Redis becomes **strongly recommended** for the auto-approval feature,
  though the platform still runs without it (fallback to Postgres counts).
- Three new tables require migrations.
- New shared package `shared/governance/`.
- The dashboard gains **Policies**, **Decisions**, and **Entity Lists**
  pages.
- `POST /incidents` response gains an `auto_approval` object.

## Alternatives considered

- **Async evaluation via job queue** — rejected: adds a worker process,
  a queue, and eventual-consistency bugs for a feature whose latency is
  already single-digit milliseconds.
- **Postgres-only counters** — rejected: `SELECT ... FOR UPDATE` under load
  becomes the bottleneck.
- **Two policy tables** — rejected: doubles the engine and the schema.
- **H3 grid regions** — rejected: coordinators think in named regions.
