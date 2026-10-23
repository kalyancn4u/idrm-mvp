# ADR-0002 — Audit Capture Lives in the Database

**Status:** Accepted

## Context

Audit capture could happen in the application (in the ORM layer), or in the
database (in triggers). Both were considered.

## Decision

The audit table is written by the application (`shared/audit.py`), **and** a
database trigger enforces immutability. Any UPDATE or DELETE raises an
exception. The table itself has no `updated_at` or `deleted_at`.

Application-level writes mean the same shape of row is produced by FastAPI
and by Flask. The trigger means the row can never be altered — by the
application, a migration, or a manual `psql` session.

## Consequences

- Auditors can query the table with plain SQL.
- A `DELETE` from `psql` fails with a clear error message.
- `TRUNCATE` still works — an intentional escape hatch for development.
- The trigger fires in the same transaction as the change it describes.
