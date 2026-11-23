# IDRM MVP — Integrated Disaster Response Management

> A map-driven platform connecting disaster-affected people with the
> organizations that can help them — plus a **staff console** for the
> coordinators who run the response.

**One repository. One database. Two apps. Shared Python.**

| App | Framework | Port | Canvas | Serves |
|---|---|---|---|---|
| **Public API** | FastAPI | :8000 | Cool slate | Citizens, providers, third parties |
| **Staff Console** | Flask | :5000 | **Warm saffron** | Coordinators and administrators |

---

## What this is

During floods, cyclones and other disasters in India today, **communication is
fragmented**, **coordination is manual**, and there is **no transparency** for
citizens. IDRM fixes this with one map-based platform.

| Actor | Does |
|---|---|
| **Citizen** | Raises a help request (incident) with a location |
| **Provider** | Sees nearby requests, claims one, delivers help |
| **Volunteer** | Not a separate role: a *provider* who self-enrolls into an organization, event, or region; a coordinator approves |
| **Coordinator** | Uses the Dispatch Console; approves, dispatches, verifies |
| **Admin** | Manages users, roles, and governance |

---

## Quick start

```bash
git clone <your-repo-url> idrm-mvp
cd idrm-mvp
bash scripts/bootstrap.sh
make run
```

- **API docs** → http://127.0.0.1:8000/docs
- **Staff console** → http://127.0.0.1:5000/dashboard/auth/login

### Demo credentials

| App | Role | Email | Password |
|---|---|---|---|
| Both | Admin | `admin@idrm.local` | `Admin#2026` |
| Dashboard | Coordinator (Hyderabad) | `coord.hyd@idrm.local` | `IDRMseed#2026` |
| Dashboard | Coordinator (Vijayawada) | `coord.vja@idrm.local` | `IDRMseed#2026` |
| API | Citizen | `priya.citizen@example.com` | `IDRMseed#2026` |
| API | Provider | `smilinghearts@ngo.example` | `IDRMseed#2026` |

---

## The two apps, visually differentiated

| | FastAPI (public) | Staff Console (Flask) |
|---|---|---|
| Background | `#f8fafc` (cool slate) | **`#fff7ed` (pale saffron)** |
| Accent | none | `#f97316` on active nav rail |
| Feel | Informational, public, calm | Operational, warm, "the war room" |

Same components. Same typography. Same accessibility (WCAG AAA). One canvas
change tells the operator *"this is the console — you can act here"* in a
single glance.

---

## Repository map

```
idrm-mvp/
├── Makefile                 run-api / run-dashboard / run
├── shared/                  code imported by BOTH apps
│   ├── config.py            one typed Settings
│   ├── security.py          bcrypt + RS256 JWT with jitter
│   ├── sessions.py          session lifecycle (the "field check")
│   ├── db.py                async (FastAPI) + sync (Flask) engines
│   ├── cache.py             optional Redis with graceful degradation
│   ├── governance/          auto-approval + entity lists
│   ├── services/            shared business logic
│   └── models/              56 ORM models (60 tables in the database)
├── app/                     FastAPI — public JSON API
│   ├── main.py
│   ├── core/                dependencies, errors, pagination
│   └── modules/             13 router modules
├── dashboard/               Flask — staff console (WARM SAFFRON)
│   ├── __init__.py          create_dashboard()
│   ├── security.py          RBAC + decorators
│   ├── services/            12 read-mostly services
│   ├── blueprints/          15 route modules
│   ├── templates/           Dispatch Console + BigBoard + 20 more
│   └── static/css/          design-system.css (saffron variant)
├── alembic/                 4 migrations, one history
├── sql/                     readable DDL + sample data
├── scripts/                 bootstrap, seed, keys, run_all, smoke
├── tests/                   unit · api · dashboard · integration
└── docs/                    13 guides + 10 references + 14 ADRs + review/
```

---

## Data model

**60 tables** (56 have an ORM model; `api_keys`, `geocode_cache` and the two
`webhook_*` tables are created by migration only). Both apps read and write
the same rows.

| Layer | Tables |
|---|---|
| Identity | users, sessions, tokens, login attempts, personnel statuses, units |
| Reference | regions, organizations, members, resources, shifts, certifications |
| Transactional | incidents, incident updates, alerts, notifications, chat, dispatch |
| Operations | ICS command, lanes, run logs, inventory, trainings |
| Governance | policies, decisions, entity lists, rate limits, mutual aid, BigBoard |
| Evidence | audit_logs (append-only, DB-enforced) |

---

## The incident lifecycle

```
created ──approve──▶ approved ──accept──▶ accepted ──start──▶ in_progress
   │                    │                    │                  │
   │                    │                    │                  ▼
   └──reject──▶ rejected└──cancel────────────┴──────────▶ cancelled  completed
                                                                     │
                                                                  verify
                                                                     ▼
                                                                 verified
```

The dashboard drives `approve` / `reject` from the Dispatch Console. The
other transitions are provider / citizen actions through the public API.

**Approval comes first.** A provider can `accept` a request only once it is
`approved`. By default that means a coordinator approves it. During a
disaster, a coordinator can switch on auto-approval for a named region and a
fixed period; when the period ends, requests wait for a coordinator again.
See [ADR-0014](docs/adr/0014-approval-first.md).

---

## Auto-approval and governance

Auto-approval is **off unless someone switches it on**. A coordinator can
turn it on for a specific region for a stipulated period (an admin can also
create wider policies). While it is on, matching low-risk incidents are
approved the moment they are created — with caps and an auditable decision
record. Outside that region or period, every request waits for a coordinator.

```
Create → Region lookup (ST_Covers) → Policy match → Caps (Redis Lua)
       → Record decision → If approved, status jumps to 'approved'
```

Every decision — approval, deferral, skip — is written to
`auto_approval_decisions` with the counters at decision time.

Read more in [docs/12-governance.md](docs/12-governance.md).

---

## Authentication: two tokens, one field check

| Token | Lifetime |
|---|---|
| Access | 30–120 min, ± 5–20 min jitter |
| Refresh | 30–180 days, ± 3–7 days jitter, sliding |

Every request checks `sid` (session alive?) and `ver` (token current?).
Blacklist bumps `users.token_version`, which invalidates every token issued
before the bump.

**Why generous TTLs are safe:** because revocation is immediate. Jitter
spreads the load so 5,000 users don't refresh at the same second.

Read more in [docs/13-auth-and-sessions.md](docs/13-auth-and-sessions.md).

---

## Databases

| Database | Required? | Purpose |
|---|---|---|
| **PostgreSQL 16 + PostGIS 3.4** | **YES** | Single source of truth |
| **MinIO** | **YES** for uploads | Object storage |
| **Redis** | **Optional** | Cache + counters. The platform runs without it |

**PostgreSQL extensions:** `postgis`, `pgcrypto` (required);
`pg_trgm`, `unaccent` (recommended).

---

## Make targets

```
make help              Show every target
make setup             venv + install + keys + infra + db + migrate + seed
make run               BOTH apps
make run-api           FastAPI on :8000
make run-dashboard     Flask on :5000
make serve             BOTH in production mode

make infra-up          Start PostGIS + MinIO + Redis
make infra-down        Stop them
make migrate           Apply Alembic migrations
make seed              Load DEMO data (development only)
make seed-reference    Load regions only (safe for production)
make db-reset          DESTRUCTIVE full rebuild
make psql              Interactive SQL
make dump              pg_dump to backups/

make routes            List routes for BOTH apps
make stats             Row counts

make test-db           Create + migrate + seed the test database (idrm_test)
make test              Full test suite (uses idrm_test, never the dev database)
make test-api          FastAPI tests
make test-dashboard    Flask tests
make test-no-redis     Prove it works without Redis
make test-cov          Coverage report
make lint              ruff + dashboard→app boundary check
make smoke             curl BOTH apps

make clean             Remove caches
make nuke              Remove venv too
```

---

## Documentation

| # | Document |
|---|---|
| 1 | [Getting Started](docs/01-getting-started.md) |
| 2 | [Architecture](docs/02-architecture.md) |
| 3 | [Data Model](docs/03-data-model.md) |
| 4 | [API Reference](docs/04-api-reference.md) |
| 5 | [Dashboard Guide](docs/05-dashboard-guide.md) |
| 6 | [Design System](docs/06-design-system.md) |
| 7 | [Operations](docs/07-operations.md) |
| 8 | [Security](docs/08-security.md) |
| 9 | [Testing](docs/09-testing.md) |
| 10 | [Troubleshooting](docs/10-troubleshooting.md) |
| 11 | [Glossary](docs/11-glossary.md) |
| 12 | [Governance](docs/12-governance.md) |
| 13 | [Auth & Sessions](docs/13-auth-and-sessions.md) |

Plus 14 [ADRs](docs/adr/) recording every architectural decision.

**Picking this project up?** Start with [CLAUDE.md](CLAUDE.md) (standing rules and
where to look) and [docs/review/PENDING-TASKS.md](docs/review/PENDING-TASKS.md) (what is
left to do).

**Setting up a server?** See the [Infrastructure Master Plan](docs/infra/INFRASTRUCTURE-MASTER-PLAN.md):
`bash infra/install.sh` shows the plan, `bash infra/install.sh apply` carries it out.

---

<div align="center">

**IDRM MVP** · Integrated Disaster Response Management
Slate + Emerald · Warm saffron console · WCAG AAA
FastAPI + Flask · PostgreSQL + PostGIS · Redis (optional)

`make help` to begin.

</div>

