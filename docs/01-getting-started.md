# Getting Started

> **Scope:** installing and running IDRM on a development machine, from zero.  
> **Owner of:** the first-run steps (install, migrate, seed, start).  
> **See also:** [07-operations.md](07-operations.md) · [10-troubleshooting.md](10-troubleshooting.md) · [QUICK_REFERENCE.md](QUICK_REFERENCE.md)

Ten minutes from zero to a running IDRM.

## 1. What you are building

A web platform with **two apps** and **one database**:

- **FastAPI** at :8000 — the public JSON API citizens and providers use.
- **Flask** at :5000 — the staff console coordinators use.
- **PostgreSQL + PostGIS** — the single source of truth.

## 2. Prerequisites

| Requirement | Check |
|---|---|
| Python 3.11+ | `python3 --version` |
| Docker (recommended) | `docker --version` |
| **or** PostgreSQL 16 + PostGIS 3.4 | `psql --version` |
| GNU Make | `make --version` |
| curl | `curl --version` |

## 3. Install — one command

```bash
git clone <your-repo-url> idrm-mvp
cd idrm-mvp
bash scripts/bootstrap.sh
```

That runs: `make env`, `make install`, `make keys`, `make infra-up`, `make db-create`, `make migrate`, `make seed`.

## 4. Run it

```bash
make run
```

- API → **http://127.0.0.1:8000/docs**
- Dashboard → **http://127.0.0.1:5000/dashboard/auth/login**

## 5. Log in

| App | Role | Email | Password |
|---|---|---|---|
| Both | Admin | `admin@idrm.local` | `Admin#2026` |
| Dashboard | Coordinator | `coord.hyd@idrm.local` | `IDRMseed#2026` |
| API | Citizen | `priya.citizen@example.com` | `IDRMseed#2026` |
| API | Provider | `smilinghearts@ngo.example` | `IDRMseed#2026` |

The admin password is `ADMIN_INITIAL_PASSWORD` if you set one. Every other
seeded user, region and policy: [SEED_REFERENCE.md](SEED_REFERENCE.md).

## 6. What to look at

### As Admin

1. **Overview** — KPIs, incident by status and service, personnel and units.
2. **Dispatch Console** — the three-panel CAD workflow.
3. **BigBoard** — the wall display.
4. **Policies** → **Decisions** — every auto-approval decision.

### As Citizen / Provider

Use the API at `:8000/docs`:
- `POST /api/v1/auth/register` to sign up.
- `POST /api/v1/incidents` to raise a request (guest or authenticated).
- `GET /api/v1/incidents/nearby?latitude=…&longitude=…` to see what's nearby.

## 7. Reset

```bash
make db-reset
```

## 8. Next

- [Architecture](02-architecture.md) — why two apps
- [Data Model](03-data-model.md) — the tables
- [Design System](06-design-system.md) — the two canvases

