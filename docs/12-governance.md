# Governance — Auto-Approval and Entity Lists

## Auto-approval, in one minute

Low-risk incidents and low-risk providers are approved **by the system**
the moment they are created — with caps, region scoping, and an auditable
decision record.

```
Citizen creates incident
  → Region lookup (PostGIS ST_Covers)
  → Match policies by priority order
  → Attempt caps (Redis Lua, atomic; Postgres fallback)
  → Record decision + audit
  → If approved: status jumps straight to 'approved'
```

## The four-step algorithm

1. **Load** policies (cache-first, 60s TTL; Postgres fallback)
2. **Filter** by region, service type, priority, effective window
3. **Attempt caps** (atomic Lua script; rolls back if any cap exceeded)
4. **Record** the decision with counters at decision time

## Policy schema

```json
{
  "code": "IN-TG-HYD-FOOD-WATER-LOW",
  "applies_to": "incident",
  "priority": 10,
  "region_scope": ["<HYD-region-uuid>"],
  "service_types": ["food", "water"],
  "priorities_allowed": ["low", "medium"],
  "conditions": {
    "max_estimated_cost_inr": 500,
    "requester_min_trust_score": 0,
    "max_per_requester_per_day": 3
  },
  "caps": {
    "per_region_per_day": 500,
    "per_requester_per_day": 3
  }
}
```

## The kill switch

One env var: `AUTO_APPROVAL_ENABLED=0`. When off, every decision is
recorded with `decision=skipped, reason=disabled`. The off state is as
auditable as the on state.

## Failure modes

| Failure | Response |
|---|---|
| Redis down | `deferred, redis_unavailable` — human handles it |
| Cap exceeded | Try next-lower-priority policy |
| Region lookup fails | `deferred, outside_known_region` |
| Invalid policy shape | Log + skip |
| Two evaluators race | Unique constraint on `(subject_type, subject_id)` |

**Design rule:** *when in doubt, defer to a human.* Default is never "approve."

## Entity lists

| Entity type | Example |
|---|---|
| `user_id` | Ban a specific account |
| `email` | Block re-registration |
| `phone` | Block known bad actor |
| `ip_address` | Block a CIDR |
| `device_fingerprint` | Block a device |

**Evaluation order:**
1. allowlist with `allow_override` → allow
2. blocklist with `hard_block` → reject
3. blocklist with `soft_block` → allow but flag
4. watchlist → allow but log

Every match is recorded in `entity_list_matches` with the context.

