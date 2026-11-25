# Governance — Auto-Approval and Entity Lists

> **Scope:** auto-approval, policies, caps and entity lists.  
> **Owner of:** policy rules and which conditions are enforced (with [ADR-0014](adr/0014-approval-first.md)).  
> **See also:** [05-dashboard-guide.md](05-dashboard-guide.md) · [design/DATA-CONFIGURATION.md](design/DATA-CONFIGURATION.md) · [03-data-model.md](03-data-model.md)

## Auto-approval, in one minute

Where a policy is in force, low-risk incidents are approved **by the system**
the moment they are created — with caps, region scoping, and an auditable
decision record. (Provider policies can be stored, but the engine is only
called for incidents today.)

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

## Approval comes first

A provider can claim (`accept`) a request only when it is `approved`. A
request becomes approved in one of two ways:

1. A coordinator approves it (Dispatch Console, or `POST /incidents/{id}/approve`).
2. An auto-approval policy that is active **for that region, at that time**
   matches it when it is created.

If neither happens the request stays in `created` and waits for a
coordinator. That is the default. The decision and its reasons are recorded
in [ADR-0014](adr/0014-approval-first.md).

### Switching auto-approval on for a disaster

During a specific event a coordinator can turn auto-approval on for the
affected region for a fixed period:

```bash
curl -X POST $API/policies -H "Authorization: Bearer $COORDINATOR_TOKEN" \
  -H 'Content-Type: application/json' -d '{
    "code": "HYD-FLOOD-2026-11",
    "name": "Hyderabad flood — auto-approve food and water",
    "applies_to": "incident",
    "region_scope": ["<HYD-region-uuid>"],
    "service_types": ["food", "water"],
    "priorities_allowed": ["low", "medium"],
    "effective_to": "2026-11-21T18:00:00Z",
    "caps": {"per_region_per_day": 500}
  }'
```

| Who | May create |
|---|---|
| coordinator | Incident policies that name at least one region **and** have an `effective_to` end time |
| admin | Any policy, including platform-wide and open-ended ones |

When `effective_to` passes, the engine stops using the policy on its own and
new requests in that region wait for a coordinator again. A coordinator can
also switch a region-scoped policy off early from **Policies** in the console.

## Conditions the engine enforces

| Condition | Meaning |
|---|---|
| `max_estimated_cost_inr` | Skip if the request's estimated cost is higher (requests carry no cost yet, so this passes) |
| `requester_min_trust_score` | Skip if the requester's `trust_score` is lower (guests count as 0) |
| `max_priority` | Skip if the request is more urgent than this |
| `max_per_requester_per_day` | Enforced as a daily cap per requester |
| `always_reject` | A matching policy blocks auto-approval (used for a regional blackout) |

Any other condition — `time_of_day_start` / `time_of_day_end`,
`min_region_verified_providers`, `max_org_type_risk`, `requires_documents`,
`min_service_radius_km` / `max_service_radius_km`, or an unknown key — is
**not** evaluated. A policy that sets one never matches, and `POST /policies`
refuses to create it.

## The kill switch

One env var: `AUTO_APPROVAL_ENABLED=0`. When off, every decision is
recorded with `decision=skipped, reason=disabled`. The off state is as
auditable as the on state.

## Failure modes

| Failure | Response |
|---|---|
| Redis down | Caps are counted from `auto_approval_decisions` instead (global and per-region only) |
| Cap exceeded | Try next-lower-priority policy |
| Region lookup fails | `deferred, outside_known_region` |
| Invalid policy shape | Rejected with `422` when created; if one is already stored, log + skip |
| Condition the engine cannot evaluate | Policy never matches (log) — the request waits for a human |
| Two evaluators race | Unique constraint on `(subject_type, subject_id)` |

**Design rule:** *when in doubt, defer to a human.* Default is never "approve."

## Entity lists

| Entity type | Example |
|---|---|
| `user_id` | Ban a specific account |
| `email` | Block a requester's help requests |
| `phone` | Block known bad actor |
| `ip_address` | One exact address |
| `device_fingerprint` | Block a device |

**Evaluation order:**
1. allowlist with `allow_override` → allow
2. blocklist with `hard_block` → reject
3. blocklist with `soft_block` → allow but flag
4. watchlist → allow but log

Every match is recorded in `entity_list_matches` with the context.

**What is enforced today:** the requester's `email`, when a signed-in user
creates a help request. Matching is exact text. The other entity types can be
stored and listed but nothing consults them yet (not registration, not login).

