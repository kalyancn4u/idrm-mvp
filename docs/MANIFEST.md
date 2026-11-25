# Repository Manifest

A complete file-by-file inventory of the IDRM MVP repository: every file git
tracks, grouped by folder, with one line on what it is for. Use it to find a
file, or to check that a copy of the repository is complete.

**Total tracked files: 272** (`git ls-files | wc -l`, 2026-11-25).

Not listed, because git does not track them: `.env`, `keys/`, `backups/`,
`.venv/`, `__pycache__/`, `.vscode/` (editor settings stay on each machine;
see `.gitignore`).

---

## Root (21 files)

| File | Purpose |
|---|---|
| `CLAUDE.md` | Rules for AI-assisted work and the map of index files — read first |
| `instructions.md` | Pointers to reference documents and the data-design brief |
| `README.md` | Project front door |
| `CHANGELOG.md` | Release history |
| `CONTRIBUTING.md` | Contribution guide, including the import-boundary rules |
| `LICENSE` | MIT |
| `Makefile` | Master task orchestrator (`make setup`, `run`, `test`, `lint`, …) |
| `requirements.txt` | Pinned Python dependencies |
| `pyproject.toml` | ruff / pytest / coverage configuration |
| `alembic.ini` | Alembic configuration |
| `run.py` | Uvicorn entrypoint |
| `.env.example` | Every setting name with its default — copy to `.env` |
| `.gitignore` | Files git must not track |
| `.gitattributes` | LF line endings for every file (must stay at the root) |
| `.dockerignore` | Container build hygiene |
| `.editorconfig` | Editor configuration |
| `.pre-commit-config.yaml` | Pre-commit hooks |
| `docker-compose.yml` | Dev infrastructure: PostGIS + MinIO + Redis |
| `docker-compose.prod.yml.example` | Production reference |
| `Dockerfile` | Application image |
| `Procfile` | Process definitions |

## `.github/workflows/` (1 file)

| File | Purpose |
|---|---|
| `ci.yml` | Lint, boundary check, tests, docker build |

## `alembic/` (6 files)

The authoritative schema (ADR-0001). A schema change is always a new file in
`versions/`.

| File | Purpose |
|---|---|
| `env.py` | Async migration environment |
| `script.py.mako` | Migration template |
| `versions/0001_baseline.py` | 29 core tables |
| `versions/0002_resgrid.py` | 31 operational tables |
| `versions/0003_seed_admin.py` | First admin user |
| `versions/0004_touch_triggers.py` | `updated_at` triggers for the tables 0002 added |

## `sql/` (7 files)

A mirror for reading, never applied (CLAUDE.md rule 2).

| File | Purpose |
|---|---|
| `01_extensions_and_enums.sql` | PostGIS + 35 enum types |
| `02_tables.sql` | Placeholder until a real schema dump is generated (PENDING-TASKS H-3) |
| `03_indexes.sql` | Index inventory |
| `04_triggers.sql` | Append-only audit + `updated_at` triggers |
| `05_regions_and_policies.sql` | Regions + starter policies |
| `06_sample_data.sql` | Demo dataset |
| `99_reset.sql` | Destructive reset |

## `shared/` (41 files)

Code used by both apps. Imports neither app, nor FastAPI, nor Flask
(enforced by `scripts/lint_boundaries.py`).

### Top-level (15)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker + the import-boundary rule |
| `config.py` | Typed settings from `.env`, with defaults and range checks |
| `logging.py` | JSON logging + request context |
| `security.py` | bcrypt + RS256 JWT + jitter |
| `sessions.py` | Server-side session lifecycle |
| `db.py` | Async + sync database engines |
| `cache.py` | Optional Redis + read-through cache |
| `storage.py` | MinIO wrapper; short-lived download links |
| `audit.py` | Unified audit writer; masks personal values |
| `enums.py` | All 35 domain enums |
| `rate_limit.py` | Token bucket + Postgres fallback |
| `lifecycle.py` | The incident state machine (the only place states change) |
| `privacy.py` | Who sees how much of a request; snapping; summary scrubber; audit redaction (ADR-0015) |
| `geo.py` | Read a PostGIS point back as latitude/longitude |
| `notifications.py` | Builds in-app notification rows |

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

### `shared/services/` (5 files)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `personnel.py` | set_status |
| `units.py` | create, set_status, add_member, remove_member |
| `dispatch.py` | assign, offer, respond, release (async, for the API) |
| `dispatch_core.py` | Dispatch rules shared by the API and the console |

### `shared/governance/` (6 files)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `schema.py` | PolicyConditions, PolicyCaps |
| `regions.py` | find_region (ST_Covers) |
| `counters.py` | Redis Lua + Postgres fallback |
| `evaluator.py` | The four-step auto-approval algorithm |
| `entity_lists.py` | Block/allow/watch evaluation |

## `app/` (36 files)

The FastAPI JSON API (citizens, providers), port 8000.

### Top-level (2)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `main.py` | FastAPI assembly |

### `app/core/` (5 files)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `authz.py` | Ownership checks: organization and unit membership, verified organizations |
| `dependencies.py` | get_db, claims, require_role, rate limits |
| `exceptions.py` | AppError + handlers |
| `pagination.py` | Envelope + clamp |

### `app/modules/` (28 files)

`app/modules/__init__.py`, and one folder per module, each with
`__init__.py` and `router.py` (13 modules × 2 = 26), plus
`incidents/lifecycle.py`.

| Module | Files | Purpose |
|---|---|---|
| `users/` | `router.py` | Auth, users, sessions |
| `incidents/` | `router.py`, `lifecycle.py` | Requests, lifecycle actions, who-sees-what shaping; `lifecycle.py` only re-exports `shared.lifecycle` for older imports |
| `dispatch/` | `router.py` | Dispatch endpoints |
| `personnel/` | `router.py` | Personnel + units |
| `organizations/` | `router.py` | Organizations + volunteers |
| `scheduling/` | `router.py` | Shifts, trainings, calendar |
| `logistics/` | `router.py` | Inventory |
| `ics/` | `router.py` | Command, lanes, run logs |
| `comms/` | `router.py` | Messages, chat, notifications |
| `policies/` | `router.py` | Policies, decisions, entity lists |
| `files/` | `router.py` | Uploads + download links |
| `audit/` | `router.py` | Audit trail |
| `administration/` | `router.py` | Health, info, summary report |

### `app/static/` (1 file)

| File | Purpose |
|---|---|
| `css/design-system.css` | Cool slate variant |

## `dashboard/` (68 files)

The Flask staff console (coordinators, admins), port 5000.

### Top-level (3)

| File | Purpose |
|---|---|
| `__init__.py` | create_dashboard() and Flask configuration |
| `extensions.py` | db proxy, login_manager, csrf |
| `security.py` | RBAC matrix + decorators |

### `dashboard/services/` (15)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `kpi.py` | Dashboard metrics |
| `incidents.py` | List + coordinator actions |
| `dispatch.py` | Three-panel data feed (sync) |
| `personnel.py` | Personnel + units aggregation |
| `organizations.py` | List + verify + volunteers |
| `users.py` | List + role/status + force logout |
| `scheduling.py` | Shifts + trainings |
| `logistics.py` | Inventory reads |
| `ics.py` | Command board |
| `policies.py` | Policies + decisions + lists |
| `alerts.py` | Area alerts |
| `audit.py` | Audit trail |
| `bigboard.py` | Widget aggregation |
| `reports.py` | Rollups |

### `dashboard/blueprints/` (16)

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
| `dispatch/console.html` | **Dispatch Console** |
| `bigboard/index.html` | **BigBoard** |
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
| `ics/common_board.html` | ICS command board |
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
| `lint_boundaries.py` | Enforce the app ↔ dashboard and shared → app/dashboard/FastAPI/Flask import rules |
| `warm_cache.py` | Prime Redis from Postgres |

## `infra/` (7 files)

The server installer; explained in `docs/infra/INFRASTRUCTURE-MASTER-PLAN.md`.

| File | Purpose |
|---|---|
| `install.sh` | The one command to remember: picks the target and runs the installer |
| `idrm_infra.py` | The master installer (plan / apply steps) |
| `lib/common.sh` | Lines every target script shares |
| `targets/ubuntu-22.04-amd64.sh`, `ubuntu-22.04-arm64.sh`, `ubuntu-24.04-amd64.sh`, `ubuntu-24.04-arm64.sh` | One file per supported OS and CPU |

## `tests/` (20 files)

Tests that write rows are marked `pg` and run only on a `*_test` database
(CLAUDE.md rule 9).

### Top-level (2)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `conftest.py` | Fixtures; refuses to write to a non-test database |

### `tests/unit/` (7)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `test_lifecycle.py` | State machine |
| `test_security.py` | bcrypt + JWT |
| `test_policies.py` | Policy shape + matching |
| `test_entity_lists.py` | List evaluation |
| `test_privacy.py` | Who-sees-what table, snapping, grace window, summary scrubber, audit redaction |
| `test_config_privacy.py` | Privacy/retention settings: defaults, ranges, cross-checks |

### `tests/api/` (5)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `test_auth.py` | Auth contract |
| `test_incidents.py` | Incident contract |
| `test_incident_privacy.py` | Provider visibility through the API (`pg`) |
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
| `test_auto_approval.py` | Governance end to end |

## `docs/` (57 files)

Where to start: `CLAUDE.md` at the root sends you to one file in
`docs/index/`, which names the one document to read.

### Top-level (23)

| File | Purpose |
|---|---|
| `README.md` | Docs index |
| `MANIFEST.md` | This file |
| `01-getting-started.md` | Install + run |
| `02-architecture.md` | High-level design |
| `03-data-model.md` | Tables by group |
| `04-api-reference.md` | Endpoints, including who sees what |
| `05-dashboard-guide.md` | Console usage |
| `06-design-system.md` | Two canvases |
| `07-operations.md` | Runbook |
| `08-security.md` | Threat model and controls |
| `09-testing.md` | Testing guide |
| `10-troubleshooting.md` | FAQ |
| `11-glossary.md` | Vocabulary |
| `12-governance.md` | Auto-approval, policies, entity lists |
| `13-auth-and-sessions.md` | JWT + sessions |
| `TUTORIAL.md` | Guided first walk-through |
| `DEMO_SCRIPT.md` | Script for a live demo |
| `DIAGRAMS.md` | Architecture and flow diagrams |
| `QUICK_REFERENCE.md` | Commands and queries on one page |
| `CLIENT_EXAMPLES.md` | Calling the API from curl, Python, JavaScript |
| `SEED_REFERENCE.md` | What `make seed` creates |
| `SECURITY_VERIFICATION.md` | Copy-paste checks that prove each control |
| `DEPLOYMENT_CHECKLIST.md` | Before going live |

### `docs/index/` (7) — one routing page per kind of task

| File | Purpose |
|---|---|
| `BUILD.md` | Install, run, deploy, fix a setup |
| `API.md` | Endpoints, tokens, sessions |
| `DASHBOARD.md` | Console pages, permissions, styling |
| `DATA.md` | Tables, migrations, seed, data design |
| `SECURITY.md` | Threats, permissions, verification |
| `QUALITY.md` | Tests, lint, known problems, pending work |
| `WHY.md` | Reasons behind the design |

### `docs/design/` (4) — data design

| File | Purpose |
|---|---|
| `DATA-DESIGN.md` | Master: model, security, engineering, warehousing, quality, SDLC, roadmap |
| `PRIVACY-FIRST-DATA-DESIGN.md` | Privacy in depth: tiers, reveal ladder, retention (ADR-0015) |
| `DATA-WORKFLOWS.md` | Every user's tasks, step by step, with the data each step touches |
| `DATA-CONFIGURATION.md` | Defaults and settings for data, privacy and retention |

### `docs/review/` (4)

| File | Purpose |
|---|---|
| `PENDING-TASKS.md` | What is left to do, in order — the working to-do list |
| `DISCREPANCY-REGISTER.md` | Every review finding and how it was fixed |
| `INSTRUCTION-HIERARCHY.md` | How the instruction files are organised |
| `IDRM-WORKSPACE-MAP.md` | The other `~/Downloads/idrm-*` folders, and known gaps |

### `docs/infra/` (1)

| File | Purpose |
|---|---|
| `INFRASTRUCTURE-MASTER-PLAN.md` | Server installer design and use |

### `docs/adr/` (17)

| File | Decision |
|---|---|
| `README.md` | ADR index and reading order |
| `ERRATA.md` | Where accepted ADRs differ from the code |
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
| `0014-approval-first.md` | Approval first; auto-approval is a time-boxed regional switch |
| `0015-privacy-first-reveal-ladder.md` | Hide personal data by default, reveal by need |

### `docs/assets/` (1)

| File | Purpose |
|---|---|
| `.gitkeep` | Placeholder for screenshots |

---

## Verification

Check that a copy of the repository is complete:

```bash
# Count tracked files (should print 272 for this version)
git ls-files | wc -l

# Verify the build
make setup
make test
make test-no-redis
make smoke
```

If the count matches and all four commands succeed, the repository is
complete. (`find . -type f` gives a larger number: it also counts `.git/`,
`.venv/`, `__pycache__/` and other untracked files.)

When you add, move or delete a file, update its row here and the counts in
the section heading and at the top.

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
