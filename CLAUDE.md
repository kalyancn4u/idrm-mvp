# IDRM MVP — instructions

Read this first. It is deliberately short: rules that always apply, then a
table that sends you to ONE index file for the task in hand.

## What this is

Disaster-response platform. One repository, one PostgreSQL database, two apps:

- `app/` — FastAPI JSON API, port 8000 (citizens, providers)
- `dashboard/` — Flask staff console, port 5000 (coordinators, admins)
- `shared/` — models, security, sessions, governance; imported by both

PostgreSQL 16 + PostGIS. Redis optional. MinIO for uploads. Python 3.11+.

## Start here

**Unfinished work is in [docs/review/PENDING-TASKS.md](docs/review/PENDING-TASKS.md).**
Most of it is "run it for real": the fixes on this branch were never run
against a database. Do Part B of that file in order, and tick tasks off there.

## Always

1. `app/` and `dashboard/` never import each other. `shared/` imports neither,
   nor FastAPI, nor Flask. Common code goes in `shared/`.
2. Schema changes are a NEW Alembic revision. `sql/` is a mirror, never applied.
3. Roles are exactly: `citizen`, `provider`, `coordinator`, `admin`.
4. Incident states change only through `shared/lifecycle.py`. A provider may
   claim only an **approved** request (ADR-0014).
5. Check ownership, not just role: use `app/core/authz.py`.
6. Every state change writes an audit row (`shared/audit.py`).
7. `get_db` rolls back when an error is raised. If a write must survive the
   error (failed login, detected token reuse), commit before raising.
8. In async code never call a blocking cache function. Use `asafe_call`,
   `ainvalidate`, `allow_async`.
9. A test may never accept a 500 as a pass. Tests that write rows are marked
   `pg` and run only on a database named `*_test` (`make test-db`).
10. No secret in the repository. Settings names are in `.env.example`.

## How to work here

- Say what was actually run. "Compiles" and "passes without a database" are
  not "works". If something was not run, say so.
- A product decision goes into an ADR (`docs/adr/`), in plain words, quoting
  the owner. Accepted ADRs are not edited; corrections go in `docs/adr/ERRATA.md`.
- Write for a beginner: explain the reason, not just the rule.
- When a fact changes, change it in the one document that owns it and link
  from the others (owners are listed in the index files).
- Commit only when asked, on a branch, never straight to `main`.

## Where to read — open ONE, then only the document it names

| Task | Index |
|---|---|
| Install, run, deploy, build a server, fix a broken setup | [docs/index/BUILD.md](docs/index/BUILD.md) |
| API endpoints, tokens, sessions | [docs/index/API.md](docs/index/API.md) |
| Console pages, permissions, styling | [docs/index/DASHBOARD.md](docs/index/DASHBOARD.md) |
| Tables, migrations, seed data, auto-approval | [docs/index/DATA.md](docs/index/DATA.md) |
| Threats, permissions, verification | [docs/index/SECURITY.md](docs/index/SECURITY.md) |
| Tests, lint, known problems, pending work | [docs/index/QUALITY.md](docs/index/QUALITY.md) |
| Why it is built this way | [docs/index/WHY.md](docs/index/WHY.md) |
| Other `~/Downloads/idrm-*` folders; personal data and privacy | [instructions.md](instructions.md) |

`README.md`, `TUTORIAL.md`, `DEMO_SCRIPT.md`, `DIAGRAMS.md`, `MANIFEST.md` and
`CHANGELOG.md` are for people; read them only when asked.
