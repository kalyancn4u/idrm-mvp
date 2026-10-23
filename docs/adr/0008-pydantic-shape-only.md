# ADR-0008 — Pydantic Validates Shape, Not Business Values

**Status:** Accepted

## Context

Pydantic could enforce every business constraint (`max_cost ≤ 500`,
`cap ≤ 10000`). But policies are data, and adding a policy should not
require a deploy.

## Decision

Pydantic enforces:

- Field names
- Types
- Nullability
- Physically impossible bounds (`rating ≥ 1`, `email` is a valid address)

Pydantic does **not** enforce:

- Business limits (max_cost, max_per_day, cap values)
- Policy-specific constraints

Those live in the policy row. The database enforces what it can; the
evaluator enforces the rest at runtime.

## Consequences

- Adding a new policy requires **no deploy**.
- A malformed policy is caught at the DB write (a bad shape is skipped with
  a logged warning) or at the evaluator (an over-large cap simply means more
  approvals).
- The API is more permissive than the DB — intentional.

## The two-tier vocabulary

| Tier | Enforced by | Example |
|---|---|---|
| **Physical** | Pydantic | `rating` is 1–5 |
| **Business** | Policy row + evaluator | `max_cost` ≤ 500 |
