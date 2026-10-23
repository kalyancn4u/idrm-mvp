# ADR-0003 — The Audit Table Is Immutable

**Status:** Accepted

## Context

An audit log that can be edited is not an audit log.

## Decision

A `BEFORE UPDATE OR DELETE` trigger on `audit_logs` raises an exception. The
error message is explicit: *"audit_logs is append-only — UPDATE and DELETE
are forbidden"*.

Two alternatives were considered:

- **PostgreSQL rules** (`DO INSTEAD NOTHING`): silently affects 0 rows. Less
  loud, but harder to notice.
- **Application-level discipline**: relies on every developer remembering.
  Fragile.

The trigger is the loudest option and does not depend on application code.

## Consequences

- Anyone — app, DBA, rogue script — cannot tamper.
- The failure mode is an exception, not a silent no-op.
- Proving immutability is a five-second demo:
  ```sql
  UPDATE audit_logs SET action = 'x' WHERE id = (SELECT id FROM audit_logs LIMIT 1);
  -- ERROR
  ```
