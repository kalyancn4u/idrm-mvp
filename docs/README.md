# IDRM MVP Documentation

**One monorepo. Two apps. One database.**

| App | Framework | Port | Canvas |
|---|---|---|---|
| Public API | FastAPI | 8000 | Cool slate |
| Staff Console | Flask | 5000 | Warm saffron |

## Reading order

| # | Document | Time |
|---|---|---|
| 1 | [Getting Started](01-getting-started.md) | 15 min |
| 2 | [Architecture](02-architecture.md) | 20 min |
| 3 | [Data Model](03-data-model.md) | 30 min |
| 4 | [API Reference](04-api-reference.md) | 15 min |
| 5 | [Dashboard Guide](05-dashboard-guide.md) | 20 min |
| 6 | [Design System](06-design-system.md) | 15 min |
| 7 | [Operations](07-operations.md) | 20 min |
| 8 | [Security](08-security.md) | 20 min |
| 9 | [Testing](09-testing.md) | 15 min |
| 10 | [Troubleshooting](10-troubleshooting.md) | reference |
| 11 | [Glossary](11-glossary.md) | reference |
| 12 | [Governance](12-governance.md) | 20 min |
| 13 | [Auth & Sessions](13-auth-and-sessions.md) | 20 min |

## The 60-second version

**Three questions IDRM answers:**

1. **Who needs help?** — `incidents` with location and priority
2. **Who can help?** — `organizations` and `units` with service areas
3. **What happened?** — every action recorded in `audit_logs`, append-only

**Two apps, one story:**

- **FastAPI** (`app/`) — the public API citizens and providers use
- **Flask console** (`dashboard/`) — the staff UI coordinators use
- They never import each other. Both import from `shared/`.

## The 5-minute SQL tour

```sql
-- What's on fire right now?
SELECT service_type, priority, status, created_at
  FROM incidents
 WHERE status IN ('created','approved','accepted','in_progress')
 ORDER BY priority DESC, created_at DESC LIMIT 10;

-- Who's available?
SELECT u.name, ps.status
  FROM personnel_statuses ps
  JOIN users u ON u.id = ps.user_id
 WHERE ps.status = 'available';

-- Prove nothing was edited.
SELECT created_at, actor_id, action, resource_type
  FROM audit_logs ORDER BY created_at DESC LIMIT 20;
```

## ADRs

See `adr/` — 14 architecture decisions recorded.

