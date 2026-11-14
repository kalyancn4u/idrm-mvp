# Quick Reference

One page. Everything a returning developer needs.

---

## Bring it up

```bash
bash scripts/bootstrap.sh     # one-time
make run                      # API :8000, Console :5000
```

## Logins

| Role | Email | Password |
|---|---|---|
| Admin | `admin@idrm.local` | `Admin#2026` |
| Coordinator (HYD) | `coord.hyd@idrm.local` | `IDRMseed#2026` |
| Coordinator (VJA) | `coord.vja@idrm.local` | `IDRMseed#2026` |
| Citizen | `priya.citizen@example.com` | `IDRMseed#2026` |
| Provider | `smilinghearts@ngo.example` | `IDRMseed#2026` |

## URLs

| What | Where |
|---|---|
| API docs | `http://127.0.0.1:8000/docs` |
| Console | `http://127.0.0.1:5000/dashboard/auth/login` |
| Dispatch | `/dashboard/dispatch` |
| BigBoard | `/dashboard/bigboard` |
| Policies | `/dashboard/policies` |
| Decisions | `/dashboard/policies/decisions` |
| Entity Lists | `/dashboard/policies/entity-lists` |
| Audit Trail | `/dashboard/audit` |

---

## The three commands you will use most

```bash
make test         # run the whole suite
make lint         # ruff + boundary check
make db-reset     # drop and rebuild the database
```

---

## The core imports

```python
# Every model
from shared.models import (
    User, UserSession, Incident, Organization, Alert,
    Region, AutoApprovalPolicy, AutoApprovalDecision, EntityList,
    Unit, PersonnelStatusRow, DispatchAssignment, DispatchOffer,
    Shift, Training, InventoryItem, AuditLog,
)

# Security primitives
from shared.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)

# Session lifecycle
from shared.sessions import (
    create_session, validate_claims, revoke_session,
    revoke_all_for_user, bump_token_version, SecurityError,
)

# Audit (async for FastAPI, sync for Flask)
from shared.audit import log_async, log_sync

# Governance
from shared.governance import evaluator, entity_lists

# FastAPI dependencies
from app.core.dependencies import get_db, get_current_claims, require_role
from app.core.exceptions import AppError

# Flask
from dashboard.extensions import db, login_manager, csrf
from dashboard.security import permission_required, admin_required
```

---

## Incident lifecycle (the state machine)

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

| Action | From | To | Who |
|---|---|---|---|
| `approve` | created | approved | coordinator, admin |
| `reject` | created, approved | rejected | coordinator, admin |
| `accept` | approved | accepted | provider |
| `start` | accepted | in_progress | provider |
| `complete` | in_progress | completed | provider |
| `verify` | completed | verified | citizen |
| `cancel` | created, approved, accepted, in_progress | cancelled | citizen, coordinator, admin |

---

## API conventions

**Auth header:**
```
Authorization: Bearer <access_token>
```

**List response:**
```json
{
  "data": [ ... ],
  "pagination": { "page": 1, "limit": 20, "total": 142, "total_pages": 8 }
}
```

**Error response:**
```json
{
  "error": {
    "code": "not_found",
    "message": "Incident not found.",
    "details": {}
  }
}
```

**Status codes:**
- `401` — missing/expired/revoked token
- `403` — role not permitted
- `404` — resource not found
- `409` — state conflict (`invalid_transition`, `already_accepted`)
- `422` — validation error
- `429` — rate limited

---

## Token TTLs

| Role | Access TTL | Refresh TTL | Max sessions | Idle timeout |
|---|---|---|---|---|
| citizen | 120 min ± 20 | 180 days ± 7 | 2 | 90 days |
| provider | 120 min ± 20 | 180 days ± 7 | 3 | 90 days |
| coordinator | 60 min ± 10 | 90 days ± 5 | 3 | 12 hours |
| admin | 30 min ± 5 | 30 days ± 3 | 2 | 4 hours |

---

## Database

**PostgreSQL 16 + PostGIS 3.4.** 60 tables. Two databases in dev:
`idrm_db` (dev) and `idrm_test` (tests).

**Spatial queries:**
```sql
-- Incidents near a point
SELECT id, description
  FROM incidents
 WHERE ST_DWithin(location::geography,
                  ST_SetSRID(ST_MakePoint(78.48, 17.40), 4326)::geography,
                  5000);   -- metres; without ::geography the unit is degrees

-- Region containing a point
SELECT code, name FROM regions
 WHERE ST_Covers(boundary, ST_SetSRID(ST_MakePoint(78.48, 17.40), 4326));
```

**Audit trail:**
```sql
SELECT created_at, actor_id, action, resource_type, resource_id
  FROM audit_logs
 ORDER BY created_at DESC
 LIMIT 20;
```

**Audit is append-only:**
```sql
UPDATE audit_logs SET action = 'x' WHERE id = (SELECT id FROM audit_logs LIMIT 1);
-- ERROR: audit_logs is append-only — UPDATE and DELETE are forbidden
```

---

## Common Make targets

```
make help              every target
make run               both apps
make run-api           FastAPI only
make run-dashboard     Flask only
make test              full suite
make test-no-redis     prove optionality
make lint              ruff + boundary check
make fmt               auto-format
make migrate           apply migrations
make revision m="…"    autogenerate a migration
make seed              load DEMO data (dev only)
make seed-reference    regions only
make test-db           create the idrm_test database
make db-reset          drop and rebuild
make psql              interactive SQL
make dump              pg_dump to backups/
make routes            list all routes (both apps)
make stats             row counts
make smoke             curl both apps
```

---

## Environment variables you will touch

```dotenv
# Required
DATABASE_URL=postgresql+asyncpg://...
DATABASE_URL_SYNC=postgresql+psycopg2://...
DASHBOARD_SECRET_KEY=...            # console session signing
ADMIN_INITIAL_PASSWORD=...          # first admin; required in production

# Optional
REDIS_URL=redis://localhost:6379/0    # leave empty to disable cache
AUTO_APPROVAL_ENABLED=1               # 0 to disable auto-approval
```

Everything else has a sensible default in `shared/config.py`.

---

## The files you will edit most

| Task | File |
|---|---|
| Add a model | `shared/models/*.py` + `shared/models/__init__.py` |
| Add an endpoint | `app/modules/*/router.py` |
| Add a console page | `dashboard/blueprints/*.py` + `dashboard/templates/*.html` |
| Add a policy field | `shared/governance/schema.py` |
| Change a design token | `dashboard/static/css/design-system.css` and `app/static/css/design-system.css` |

---

## When something breaks

```bash
# Is the API up?
curl -fsS http://localhost:8000/api/v1/health | jq

# Is the DB up?
make psql
SELECT 1;

# What did the app log?  (JSON lines on stdout — there is no log file)
docker logs -f idrm-api      # or look at the terminal running `make run`

# What route am I hitting?
make routes
```

---

## Debug checklist

| Symptom | First thing to check |
|---|---|
| 401 on every request | Is the token expired? `decode_token` locally |
| 403 on the console | Your role must be `coordinator` or `admin` |
| Auto-approval not firing | `/dashboard/policies` — is the policy active? |
| Rate limited (429) | Wait 60 seconds |
| Dashboard shows cool slate | You're on the API, not the console |
| Migrations fail | `make db-reset` (dev only) |

Full troubleshooting in [10-troubleshooting.md](10-troubleshooting.md).
