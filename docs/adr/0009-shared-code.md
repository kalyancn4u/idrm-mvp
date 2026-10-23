# ADR-0009 — Shared Code Lives in `shared/`

**Status:** Accepted

## Context

Two apps (FastAPI, Flask) operate on the same data. Without an explicit
shared package, they would each have their own models, security helpers,
and database connections — the classic "two apps diverged" problem.

## Decision

A single `shared/` package holds:

- `shared/models/` — the ORM. Both apps import from here.
- `shared/security.py` — bcrypt + JWT. Both use the same primitives.
- `shared/sessions.py` — session lifecycle.
- `shared/db.py` — async engine for FastAPI, sync engine for Flask.
- `shared/audit.py` — unified audit writer.
- `shared/governance/` — auto-approval + entity lists.
- `shared/services/` — business logic that both apps share.
- `shared/config.py` — one Settings class.

Neither app owns the other's code. The boundary is enforced by convention
and by `make lint`, which fails if `dashboard/**` imports from `app/**`.

## Consequences

- The models are the same object in both apps. `User` is `User`.
- A change to a model requires no change in either app.
- A helper in `shared/` cannot import from FastAPI or Flask — it must be
  framework-agnostic.
- `make lint` is the enforcement mechanism.
