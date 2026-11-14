# Architecture

## The two-app monolith

```
              FastAPI :8000                Flask :5000
              (public JSON)                (staff HTML)
                    │                            │
                    └──────────────┬─────────────┘
                                   │
                              shared/
                          models, security,
                          sessions, governance
                                   │
                 ┌─────────────────┼─────────────────┐
                 │                 │                 │
           PostgreSQL          MinIO            Redis
          (+ PostGIS)         (uploads)        (optional)
```

Both apps:
- Import from `shared/**`
- Never import each other
- Connect to the same database
- Write to the same `audit_logs` table

## Why two apps

| Reason | Detail |
|---|---|
| Different audiences | Public API vs. staff console |
| Different renderers | JSON vs. HTML |
| Different ports | 8000 vs. 5000 |
| Same data | Identical ORM models |
| Boundary | `make lint` rejects `dashboard → app` imports |

## Key ADRs

| # | Decision |
|---|---|
| 0001 | SQL files are the source of truth for the schema |
| 0002 | Audit capture lives in the database |
| 0003 | The audit table is immutable (trigger) |
| 0004 | Redis is an optional cache |
| 0005 | Two-app monolith |
| 0006 | Dashboard is read-mostly |
| 0007 | Auto-approval is policy-driven |
| 0008 | Pydantic validates shape, DB validates values |
| 0009 | Shared code lives in `shared/` |
| 0010 | All sessions are server-tracked |
| 0011 | Entity lists are one table |
| 0012 | Volunteer enrollment is scope-based |
| 0013 | Two-token JWT with session check |
| 0014 | Approval comes first; coordinators may auto-approve a region for a fixed period |

## Data flow — an auto-approved incident

```
1. Citizen POSTs /api/v1/incidents
2. Entity-list check on requester email
3. INSERT incident (status='created')
4. INSERT incident_updates
5. INSERT audit_logs (action='incident.created')
6. governance.evaluator.decide()
   a. find_region(location) via ST_Covers
   b. load active policies (cache-first)
   c. try_acquire_caps (Redis Lua, atomic)
   d. INSERT auto_approval_decisions
7. If approved → UPDATE incident SET status='approved'
              → INSERT incident_updates
              → INSERT audit_logs (action='incident.auto_approved')
8. Response includes `"auto_approved": true` and `"status": "approved"`
```

## Deployment

| Environment | API | Dashboard |
|---|---|---|
| Development | uvicorn --reload | flask --debug |
| Production | gunicorn + UvicornWorker (4) | gunicorn (4) |

(`Procfile` is a lighter single-host profile: one uvicorn process and two
dashboard workers.)

Redis is optional. When absent:
- Session lookups fall through to Postgres
- Rate limits fall back to an in-process counter (per worker process)
- Auto-approval counters count from `auto_approval_decisions`
- The platform is slower, never broken

