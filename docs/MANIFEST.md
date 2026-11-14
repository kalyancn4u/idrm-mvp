# Repository Manifest

A complete file-by-file inventory of the IDRM MVP repository. Use this to
verify that every artifact has been transcribed correctly.

**Total files: 227.**

---

## Root (18 files)

| File | Purpose |
|---|---|
| `Makefile` | Master task orchestrator |
| `README.md` | Project front door |
| `requirements.txt` | Pinned Python dependencies |
| `pyproject.toml` | ruff / pytest / coverage configuration |
| `alembic.ini` | Alembic configuration |
| `.env.example` | Environment contract |
| `.gitignore` | Repo hygiene |
| `.dockerignore` | Container build hygiene |
| `.editorconfig` | Editor configuration |
| `.pre-commit-config.yaml` | Pre-commit hooks |
| `docker-compose.yml` | Dev infrastructure: PostGIS + MinIO + Redis |
| `docker-compose.prod.yml.example` | Production reference |
| `Procfile` | Process definitions |
| `Dockerfile` | Application image |
| `run.py` | Uvicorn entrypoint |
| `LICENSE` | MIT |
| `CHANGELOG.md` | Release history |
| `CONTRIBUTING.md` | Contribution guide |

## `.github/workflows/` (1 file)

| File | Purpose |
|---|---|
| `ci.yml` | Lint + test + docker build |

## `.vscode/` (2 files)

| File | Purpose |
|---|---|
| `settings.json` | Editor configuration |
| `extensions.json` | Recommended extensions |

## `alembic/` (6 files)

| File | Purpose |
|---|---|
| `env.py` | Async migration environment |
| `script.py.mako` | Migration template |
| `versions/0001_baseline.py` | 29 core tables |
| `versions/0002_resgrid.py` | 31 operational tables |
| `versions/0003_seed_admin.py` | First admin user |
| *(README implied)* | — |

## `sql/` (7 files)

| File | Purpose |
|---|---|
| `01_extensions_and_enums.sql` | PostGIS + 34 enums |
| `02_tables.sql` | DBA-facing DDL snapshot |
| `03_indexes.sql` | Index inventory |
| `04_triggers.sql` | Append-only + updated_at triggers |
| `05_regions_and_policies.sql` | Regions + starter policies |
| `06_sample_data.sql` | Demo dataset |
| `99_reset.sql` | Destructive reset |

## `shared/` (38 files)

### Top-level (12)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `config.py` | Typed Settings |
| `logging.py` | JSON logging + context |
| `security.py` | bcrypt + RS256 JWT + jitter |
| `sessions.py` | Session lifecycle + field check |
| `db.py` | Async + sync engines |
| `cache.py` | Redis + read-through cache |
| `storage.py` | MinIO wrapper |
| `audit.py` | Unified audit writer |
| `enums.py` | All 22 domain enums |
| `rate_limit.py` | Token bucket + Postgres fallback |
| *(nothing else)* | — |

### `shared/models/` (15 files)

| File | Purpose |
|---|---|
| `__init__.py` | Single re-export |
| `base.py` | Declarative base + mixins |
| `identity.py` | User, UserSession, tokens, LoginAttempt |
| `incident.py` | Incident, IncidentUpdate |
| `organization.py` | Organization, Member, Resource, VolunteerEnrollment, UserDelegation |
| `dispatch.py` | DispatchAssignment, DispatchOffer |
| `personnel.py` | PersonnelStatus, Unit, UnitMember, UnitStatus + events |
| `scheduling.py` | Shift, Signup, Trade, Certification, Training, Assignment, Completion, CalendarEvent, RSVP |
| `logistics.py` | InventoryLocation, InventoryItem, InventoryTransaction |
| `ics.py` | IncidentCommand, IncidentLane, LaneAssignment, RunLog, RunLogEntry |
| `comms.py` | Message, ChatChannel, ChatMessage, Notification, Preference, Delivery |
| `governance.py` | Region, AutoApprovalPolicy, AutoApprovalDecision, EntityList, EntityListMatch, RateLimitEvent, MutualAidAgreement, BigboardConfig, BigboardWidget |
| `alert.py` | Alert |
| `file.py` | File |
| `audit.py` | AuditLog |

*(Some of these are grouped: 15 physical files under `shared/models/`.)*

### `shared/services/` (4 files)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `personnel.py` | set_status |
| `units.py` | create, set_status, add_member, remove_member |
| `dispatch.py` | assign, offer, respond, release |

### `shared/governance/` (6 files)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `schema.py` | PolicyConditions, PolicyCaps |
| `regions.py` | find_region (ST_Covers) |
| `counters.py` | Redis Lua + Postgres fallback |
| `evaluator.py` | The four-step algorithm |
| `entity_lists.py` | Block/allow/watch evaluation |

## `app/` (36 files)

### Top-level (3)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `main.py` | FastAPI assembly |
| *(nothing else)* | — |

### `app/core/` (5 files)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `dependencies.py` | get_db, claims, require_role |
| `exceptions.py` | AppError + handlers |
| `pagination.py` | Envelope + clamp |

### `app/modules/` (14 × `__init__.py`) + routers (13)

Each module has `__init__.py` and at least `router.py`. Some have additional
files.

| Module | Files |
|---|---|
| `users/router.py` | Auth + users + sessions |
| `incidents/lifecycle.py`, `router.py`, `repository.py`, `service.py` | Incident lifecycle |
| `dispatch/router.py` | Dispatch endpoints |
| `personnel/router.py` | Personnel + units |
| `organizations/router.py` | Organizations + volunteers |
| `scheduling/router.py` | Shifts + trainings + calendar |
| `logistics/router.py` | Inventory |
| `ics/router.py` | Command + lanes + run logs |
| `comms/router.py` | Messages + chat + notifications |
| `policies/router.py` | Policies + decisions + entity lists |
| `files/router.py` | Uploads |
| `audit/router.py` | Audit trail |
| `administration/router.py` | Health + info + reports |

### `app/static/` (1 file)

| File | Purpose |
|---|---|
| `css/design-system.css` | Cool slate variant |

## `dashboard/` (68 files)

### Top-level (5)

| File | Purpose |
|---|---|
| `__init__.py` | create_dashboard() |
| `config.py` | Flask-specific config |
| `extensions.py` | db proxy, login_manager, csrf |
| `security.py` | RBAC matrix + decorators |
| *(nothing else)* | — |

### `dashboard/services/` (13)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `kpi.py` | Dashboard metrics |
| `incidents.py` | List + coordinator actions |
| `dispatch.py` | Three-panel data feed |
| `personnel.py` | Personnel + units aggregation |
| `organizations.py` | List + verify + volunteers |
| `users.py` | List + role/status + force logout |
| `scheduling.py` | Shifts + trainings |
| `logistics.py` | Inventory reads |
| `ics.py` | Command board |
| `policies.py` | Policies + decisions + lists |
| `audit.py` | Audit trail |
| `bigboard.py` | Widget aggregation |
| `reports.py` | Rollups |

### `dashboard/blueprints/` (15)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `auth.py` | Sign in / out |
| `main.py` | Overview |
| `dispatch.py` | Console + actions |
| `bigboard.py` | Widget grid + data |
| `incidents.py` | List + detail + approve/reject |
| `personnel.py` | Status overview |
| `organizations.py` | List + verify + volunteers |
| `users.py` | List + detail + role/status/logout |
| `scheduling.py` | Shifts + trainings |
| `logistics.py` | Inventory |
| `ics.py` | Command board |
| `policies.py` | List + toggle + decisions + entity lists |
| `alerts.py` | List + create + deactivate |
| `audit.py` | Trail |
| `reports.py` | Rollups + CSV export |

### `dashboard/templates/` (31 files)

| File | Purpose |
|---|---|
| `base.html` | Layout shell |
| `components/_macros.html` | kpi, pri_badge, status_badge, reltime, empty_state, pager, page_head |
| `components/_sidebar.html` | Role-aware nav |
| `auth/login.html` | Login page |
| `main/dashboard.html` | Overview |
| `dispatch/console.html` | **Dispatch Console** (crown jewel) |
| `bigboard/index.html` | **BigBoard** (crown jewel) |
| `incidents/list.html` | Incident list |
| `incidents/detail.html` | Incident detail + timeline |
| `personnel/status.html` | Personnel + units |
| `organizations/list.html` | Org list |
| `organizations/detail.html` | Org detail |
| `organizations/volunteers.html` | Pending volunteers |
| `users/list.html` | User list |
| `users/detail.html` | User detail + sessions |
| `scheduling/shifts.html` | Shifts |
| `scheduling/trainings.html` | Trainings |
| `scheduling/certifications.html` | Expiring certifications |
| `logistics/inventory.html` | Inventory |
| `ics/command_board.html` | ICS command board |
| `policies/list.html` | Policies |
| `policies/decisions.html` | Decisions |
| `policies/entity_lists.html` | Entity lists |
| `alerts/list.html`, `alerts/create.html` | Alerts |
| `audit/trail.html` | Audit trail |
| `reports/index.html`, `reports/response_times.html` | Reports |
| `errors/403.html`, `errors/404.html`, `errors/500.html` | Error pages |

### `dashboard/static/` (3 files)

| File | Purpose |
|---|---|
| `css/design-system.css` | **Warm saffron variant** |
| `js/app.js` | Client behaviour |
| `img/logo.svg` | Logo |

## `scripts/` (8 files)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `seed.py` | Idempotent seed |
| `generate_keys.py` | RS256 keypair |
| `bootstrap.sh` | One-shot bring-up |
| `run_all.sh` | Both apps in one shell |
| `smoke.sh` | Curl both apps |
| `lint_boundaries.py` | Enforce dashboard→app rule |
| `warm_cache.py` | Prime Redis from Postgres |

## `tests/` (17 files)

### `tests/` (1)

| File | Purpose |
|---|---|
| `conftest.py` | Fixtures |

### `tests/unit/` (7)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `test_lifecycle.py` | State machine |
| `test_security.py` | bcrypt + JWT |
| `test_policies.py` | Policy shape + matching |
| `test_entity_lists.py` | List evaluation |
| *(more)* | — |

### `tests/api/` (4)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `test_auth.py` | Auth contract |
| `test_incidents.py` | Incident contract |
| `test_dispatch.py` | Dispatch contract |

### `tests/dashboard/` (3)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `test_rbac.py` | Access control |
| `test_bigboard.py` | BigBoard |

### `tests/integration/` (3)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `test_no_redis.py` | Optionality proof |
| `test_auto_approval.py` | Governance e2e |

## `docs/` (43 files)

### Top-level (14)

| File | Purpose |
|---|---|
| `README.md` | Docs index |
| `MANIFEST.md` | This file |
| `01-getting-started.md` | Install + run |
| `02-architecture.md` | HLD |
| `03-data-model.md` | Tables |
| `04-api-reference.md` | Endpoints |
| `05-dashboard-guide.md` | Console usage |
| `06-design-system.md` | Two canvases |
| `07-operations.md` | Runbook |
| `08-security.md` | Threat model |
| `09-testing.md` | Testing guide |
| `10-troubleshooting.md` | FAQ |
| `11-glossary.md` | Vocabulary |
| `12-governance.md` | Auto-approval |
| `13-auth-and-sessions.md` | JWT + sessions |

### `docs/adr/` (14)

| File | Decision |
|---|---|
| `README.md` | ADR index |
| `0001-sql-as-source-of-truth.md` | Schema in migrations |
| `0002-audit-in-database.md` | Audit capture |
| `0003-immutable-audit.md` | Append-only enforcement |
| `0004-redis-optional.md` | Optional cache |
| `0005-two-app-monolith.md` | Two-app structure |
| `0006-dashboard-read-mostly.md` | Small write surface |
| `0007-auto-approval.md` | Policy-driven |
| `0008-pydantic-shape-only.md` | Shape validation |
| `0009-shared-code.md` | shared/ package |
| `0010-server-tracked-sessions.md` | Session tracking |
| `0011-unified-entity-lists.md` | One table |
| `0012-scope-based-volunteers.md` | Enrollment |
| `0013-jwt-two-token.md` | Two-token JWT |

### `docs/assets/` (1)

| File | Purpose |
|---|---|
| `.gitkeep` | Placeholder for screenshots |

---

## Verification

After transcribing the repository, run:

```bash
# Count files (should be ~227 excluding .git/ and .venv/)
find . -type f -not -path './.git/*' -not -path './.venv/*' | wc -l

# Verify the build
make setup
make test
make test-no-redis
make smoke
```

If all four commands succeed, the repository is complete.

---

## The five-command tour

For a novice, this is the whole answer:

```bash
git clone <repo> idrm-mvp && cd idrm-mvp
bash scripts/bootstrap.sh
make run
# Open http://127.0.0.1:8000/docs      (API)
# Open http://127.0.0.1:5000/dashboard/auth/login   (Console)
# Log in as admin@idrm.local / Admin#2026
```

Everything else is documented in `docs/`.
