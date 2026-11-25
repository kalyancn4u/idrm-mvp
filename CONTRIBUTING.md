# Contributing to IDRM

Thank you for considering a contribution. This guide explains how the
repository is organised, how to set up a development environment, and the
conventions that keep the codebase coherent.

---

## Code of conduct

Be respectful. Assume good faith. Focus on the work.

---

## Getting started

```bash
git clone <your-fork-url> idrm-mvp
cd idrm-mvp
bash scripts/bootstrap.sh
make run
```

See [docs/01-getting-started.md](docs/01-getting-started.md) for details.

---

## Repository layout

```
app/         FastAPI — the public JSON API
dashboard/   Flask  — the staff console
shared/      Code imported by BOTH apps
alembic/     Migrations
sql/         Readable DDL (DBA-facing)
tests/       Test suite
docs/        Documentation
```

### The boundary rule

| Rule | Enforced by |
|---|---|
| `app/**` may import from `shared/**` | allowed |
| `dashboard/**` may import from `shared/**` | allowed |
| `dashboard/**` must NOT import from `app/**` | `scripts/lint_boundaries.py` (fails `make lint` and CI) |
| `app/**` must NOT import from `dashboard/**` | `scripts/lint_boundaries.py` (fails `make lint` and CI) |
| `shared/**` must NOT import from `app/**`, `dashboard/**`, FastAPI (or Starlette) or Flask (or any `flask_*`) | `scripts/lint_boundaries.py` (fails `make lint` and CI) |

The checker parses each file, so it finds imports written over several lines
or inside functions and ignores the same words in comments and strings. It
does not see dynamic imports (`importlib.import_module("app")`) — do not use
them to get around the rule.

If you find yourself wanting to break the rule, the correct answer is almost
always: *move the code to `shared/`*.

---

## Development workflow

### 1. Create a branch

```bash
git checkout -b feat/your-feature-name
# or
git checkout -b fix/short-description
```

Branch name prefixes we use: `feat/`, `fix/`, `docs/`, `refactor/`,
`test/`, `chore/`.

### 2. Make your changes

Follow the [Conventions](#conventions) below.

### 3. Run the pre-PR gate

```bash
make fmt       # auto-format
make lint      # ruff + boundary check
make test      # full test suite
make test-no-redis   # prove the platform still works without Redis
```

All four must pass before you open a pull request.

### 4. Commit

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(dispatch): add bulk-assign action
fix(auth): reject refresh tokens past their family TTL
docs(readme): clarify the two-canvas design
refactor(shared): move rate limiter to shared/rate_limit.py
test(incidents): cover the verify transition
chore(ci): cache pip wheels
```

The body of the commit message should explain *why*, not *what*.

### 5. Open a pull request

Include:

- **A summary** — one paragraph.
- **A test plan** — what you ran and what you saw.
- **Screenshots** — if the change is visible in either UI.
- **A link to any related issue**.

---

## Conventions

### Python

- **Line length:** 100 characters.
- **Imports:** sorted by `ruff` (isort-compatible).
- **Type hints:** on all function signatures in `shared/` and `app/`.
- **Docstrings:** on all public functions in `shared/`. One-line summary,
  blank line, longer description if needed. No docstring is fine for
  trivial private helpers.
- **Async:** `async def` in `app/` and `shared/services/`. Sync def in
  `dashboard/` and `shared/models/`.
- **No `from x import *`.**

### Naming

| Thing | Convention | Example |
|---|---|---|
| Python module | `lower_snake.py` | `rate_limit.py` |
| Python class | `PascalCase` | `AutoApprovalPolicy` |
| Python function | `lower_snake()` | `set_personnel_status` |
| Pydantic model | `PascalCase` ending in `Request`/`Response`/`Body` | `LoginRequest` |
| SQLAlchemy model | `PascalCase` | `UserSession` |
| Database table | `lower_snake`, plural | `user_sessions` |
| Database column | `lower_snake` | `refresh_token_hash` |
| Enum | `PascalCase` (Python), `lower_snake` (SQL) | `IncidentStatus` / `incident_status` |
| Flask blueprint | `lower_snake_bp` | `dispatch_bp` |
| Route | `/kebab-case` | `/auto-approval` |

### Database

- New tables have `id` (UUID) and `created_at`; mutable ones also have
  `updated_at` **and** the `set_updated_at()` trigger (see migration `0004`).
- Every soft-deleted table has `deleted_at` (nullable timestamptz).
- Index a foreign key column when queries filter or join on it.
- Every enum is created at the database level, not as a `CHECK` constraint.
- Every schema change is a migration. Never edit an applied migration.

### Migrations

- One logical change per migration.
- Migrations must be reversible (`downgrade()` implemented).
- Data migrations use `NOT EXISTS` guards to be idempotent.
- Never modify an applied migration — create a new one.

### Tests

- One test file per source module.
- Names describe behaviour: `test_rejects_expired_token_not_just_wrong_signature`.
- Use the fixtures in `conftest.py`; do not create ad-hoc clients.
- Mark DB-dependent tests with `@pytest.mark.pg`.
- Mark Redis-dependent tests with `@pytest.mark.requires_redis`.

### Documentation

- Every new feature updates at least one doc file.
- Every architectural decision gets an ADR in `docs/adr/`.
- Operator-facing changes update the runbook.
- Security-relevant changes update `docs/08-security.md`.

---

## Adding a new API endpoint

1. Add a Pydantic schema next to the handler (schemas currently live at the
   top of each `router.py`).
2. Add the route handler in the module's `router.py`.
3. If it writes, add an audit event via `shared.audit.log_async`.
3b. Check *ownership*, not only role: use the helpers in `app/core/authz.py`.
4. Add a test in `tests/api/`.
5. Update `docs/04-api-reference.md`.

## Adding a new dashboard page

1. Add a service method (read-mostly) in `dashboard/services/`.
2. Add a route in the appropriate blueprint.
3. Add a template extending `base.html`.
4. Import the macros from `components/_macros.html`.
5. Add a test in `tests/dashboard/`.
6. Update `docs/05-dashboard-guide.md`.

## Adding a new policy type

1. Add the field to `shared/governance/schema.py`'s `PolicyConditions`
   or `PolicyCaps`.
2. Enforce it in `shared/governance/evaluator.py`'s `_matches_conditions`
   or in the cap counters.
3. Add a unit test to `tests/unit/test_policies.py`.
4. Document it in `docs/12-governance.md`.

---

## Reviewing a pull request

Check:

- [ ] Does it pass CI?
- [ ] Is the boundary rule respected?
- [ ] Is there a test?
- [ ] Is there a doc update?
- [ ] If it's a schema change, is it a new migration?
- [ ] If it writes, does it audit?
- [ ] If it's user-visible, does it follow the design system?
- [ ] Is the commit message conventional?

---

## Reporting a bug

Open an issue with:

- **What you did**
- **What you expected**
- **What happened**
- **Version** (git SHA, or tag)
- **Environment** (OS, Python version, Postgres version)
- **Logs** (JSON lines from the app's stdout, and the `X-Request-ID` of the failing response)

If the bug is security-relevant, do not open a public issue — email the
maintainers directly.

---

## License

By contributing, you agree that your contributions are licensed under the
same MIT License that covers the project. See [LICENSE](LICENSE).
