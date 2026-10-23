# ADR-0001 — SQL Files Are the Source of Truth for the Schema

**Status:** Accepted

## Context

Two apps (FastAPI, Flask) share one database. The ORM has models, but
`db.create_all()` is not called — migrations are.

## Decision

The schema lives in **Alembic migrations** (mirrored by readable `sql/*.sql`
files for DBAs). The ORM models must match. A DBA can read the schema
without reading Python.

## Consequences

- Schema is reviewable in a pull request as plain SQL.
- `make migrate` is the only way to change the schema.
- Autogenerate is safe because both apps use the same `Base.metadata`.

