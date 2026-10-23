# Diagrams

Every diagram in one place, in plain ASCII so it renders in any terminal,
any code review, any Markdown viewer.

---

## 1. The platform

```
                        ┌──────────────────────────────┐
   Citizens /           │       Public Internet        │
   Providers            └───────────────┬──────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    │                                       │
            ┌───────▼────────┐                    ┌─────────▼─────────┐
            │   FastAPI MVP  │                    │  Flask Dashboard  │
            │   :8000        │                    │  :5000            │
            │                │                    │                   │
            │  /api/v1/*     │                    │  /dashboard/*     │
            │  JSON only     │                    │  HTML + forms     │
            │                │                    │                   │
            │  async SQLAlchemy                  │  sync SQLAlchemy  │
            │  (asyncpg)     │                    │  (psycopg2)       │
            └───────┬────────┘                    └─────────┬─────────┘
                    │                                       │
                    └───────────────────┬───────────────────┘
                                        │
                                ┌───────▼────────┐
                                │  shared/       │
                                │  models        │
                                │  security      │
                                │  db factories  │
                                │  governance    │
                                └───────┬────────┘
                                        │
                        ┌───────────────┴───────────────┐
                        │                               │
                ┌───────▼───────┐              ┌────────▼────────┐
                │ PostgreSQL    │              │     MinIO       │
                │ + PostGIS     │              │  (uploads)      │
                │  (60 tables)  │              │                 │
                └───────────────┘              └─────────────────┘
                        │
                ┌───────▼───────┐
                │     Redis     │  ← optional cache
                │  (sessions,   │
                │   counters)   │
                └───────────────┘
```

---

## 2. The two apps — visual identity

```
   FastAPI :8000                       Flask :5000
   ────────────────                    ─────────────
   ┌──────────────────────────┐        ┌──────────────────────────┐
   │ cool slate #f8fafc       │        │ warm saffron #fff7ed     │
   │                          │        │                          │
   │ API docs at /docs        │        │ Console at               │
   │ JSON responses           │        │ /dashboard/login         │
   │                          │        │                          │
   │ ✓ informational          │        │ ✓ operational            │
   │ ✓ public                 │        │ ✓ staff-only             │
   │ ✗ no forms               │        │ ✗ no public sign-in      │
   └──────────────────────────┘        └──────────────────────────┘
             │                                    │
             └────────────────┬───────────────────┘
                              │
                    Same design system, same
                    components, same typography,
                    WCAG AAA on both.
                    Only the canvas changes.
```

---

## 3. Data model — five layers

```
   ┌─────────────────────────────────────────────────────────────┐
   │  IDENTITY                                                   │
   │  users ─┬── user_sessions                                   │
   │         ├── password_reset_tokens                           │
   │         ├── email_verification_tokens                       │
   │         ├── password_history                                │
   │         ├── login_attempts                                  │
   │         ├── personnel_statuses ─── personnel_status_events  │
   │         └── organization_members                            │
   │                                                             │
   │  units ─┬── unit_members                                    │
   │         ├── unit_statuses                                   │
   │         └── unit_status_events                              │
   └─────────────────────────────────────────────────────────────┘
                              │
   ┌─────────────────────────────────────────────────────────────┐
   │  REFERENCE                                                  │
   │  regions ──── organizations ──┬── resources                 │
   │                               ├── volunteer_enrollments     │
   │                               ├── user_delegations          │
   │                               ├── mutual_aid_agreements     │
   │                               └── api_keys                  │
   └─────────────────────────────────────────────────────────────┘
                              │
   ┌─────────────────────────────────────────────────────────────┐
   │  TRANSACTIONAL                                              │
   │  incidents ─┬── incident_updates                            │
   │             ├── dispatch_assignments                        │
   │             ├── dispatch_offers                             │
   │             └── incident_commands ─── incident_lanes        │
   │                                                             │
   │  alerts                                                     │
   │  notifications ─── notification_deliveries                  │
   │  notification_preferences                                   │
   │  chat_channels ─── chat_messages                            │
   │  messages                                                   │
   │  calendar_events ─── event_rsvps                            │
   └─────────────────────────────────────────────────────────────┘
                              │
   ┌─────────────────────────────────────────────────────────────┐
   │  OPERATIONS                                                 │
   │  shifts ─── shift_signups ─── shift_trades                  │
   │  personnel_certifications                                   │
   │  trainings ─┬── training_assignments ─── training_completions│
   │  inventory_locations ─── inventory_items ─── inventory_txns │
   │  run_logs ─── run_log_entries                               │
   │  lane_assignments                                           │
   └─────────────────────────────────────────────────────────────┘
                              │
   ┌─────────────────────────────────────────────────────────────┐
   │  GOVERNANCE + EVIDENCE                                      │
   │  auto_approval_policies ─── auto_approval_decisions         │
   │  entity_lists ─── entity_list_matches                       │
   │  rate_limit_events                                          │
   │  bigboard_configs ─── bigboard_widgets                      │
   │  geocode_cache                                              │
   │  webhook_subscriptions ─── webhook_deliveries               │
   │                                                             │
   │  audit_logs  ← append-only, DB-enforced                     │
   └─────────────────────────────────────────────────────────────┘
```

---

## 4. The incident lifecycle

```
                        ┌──────────┐
                        │ created  │◀── citizen creates (or auto-approval
                        └────┬─────┘     fires immediately and skips to
                             │           'approved')
                   ┌─────────┴─────────┐
                   │                   │
              coordinator         coordinator
                   │                   │
                approve              reject
                   │                   │
                   ▼                   ▼
              ┌──────────┐        ┌──────────┐
              │ approved │        │ rejected │  ← terminal
              └────┬─────┘        └──────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
     provider           coordinator
        │                     │
     accept                assign
        │                     │
        └──────────┬──────────┘
                   │
                   ▼
              ┌──────────┐
              │ accepted │
              └────┬─────┘
                   │
              provider
                   │
                 start
                   │
                   ▼
             ┌─────────────┐
             │ in_progress │
             └──────┬──────┘
                    │
               provider
                    │
                complete
                    │
                    ▼
              ┌───────────┐
              │ completed │
              └─────┬─────┘
                    │
                citizen
                    │
                 verify
                    │
                    ▼
              ┌──────────┐
              │ verified │  ← terminal
              └──────────┘

      From {created, approved, accepted, in_progress}:
              cancel  →  cancelled  (terminal)
```

---

## 5. Auto-approval decision flow

```
   Citizen POSTs /incidents
              │
              ▼
   ┌──────────────────────────┐
   │ Entity list check        │   hard_block → 403
   │ (email, IP, phone, …)    │
   └───────────┬──────────────┘
               │
               ▼
   ┌──────────────────────────┐
   │ INSERT incident          │
   │ status='created'         │
   └───────────┬──────────────┘
               │
               ▼
   ┌──────────────────────────┐
   │ governance.evaluator     │
   │   .decide()              │
   └───────────┬──────────────┘
               │
        ┌──────┴──────┐
        │             │
   Step 1: Region     │
   ST_Covers          │
        │             │
        ▼             │
   Step 2: Load +     │
   filter policies    │
   (cache 60s)        │
        │             │
        ▼             │
   Step 3: Caps       │
   Redis Lua atomic   │
   (Postgres fallback)│
        │             │
        ▼             │
   Step 4: Record     │
   decision row +     │
   audit event        │
        │             │
        └──────┬──────┘
               │
        ┌──────┴──────┐
        │             │
    approved       deferred
        │             │
        ▼             ▼
   UPDATE incident   Leave at 'created'
   status='approved' Coordinator handles
   auto_approved=true
```

---

## 6. Two-token JWT with session check

```
   Login
     │
     ▼
   ┌─────────────────────────────┐
   │ Verify credentials          │
   │ Enforce session limit       │
   │ INSERT user_sessions        │
   │   session_id = uuid4()      │
   │   family = uuid4()          │
   │ Mint access (sub, sid, ver) │
   │ Mint refresh (sub, sid,fam) │
   └──────────────┬──────────────┘
                  │
                  ▼
   Client stores both. Sends access on every request.
                  │
                  ▼
   ┌─────────────────────────────┐
   │ Every authenticated request │
   └──────────────┬──────────────┘
                  │
        1. Verify signature
        2. Verify exp
        3. Verify typ == "access"
                  │
                  ▼
   ┌─────────────────────────────┐
   │ Session lookup by sid       │
   │ Cache: Redis 60s TTL        │
   │ Fallback: Postgres SELECT   │
   └──────────────┬──────────────┘
                  │
        4. session.revoked_at IS NULL
        5. session.expires_at > now
        6. idle timeout not exceeded
        7. users.status == 'active'
        8. claims.ver == users.token_version   ← the field check
                  │
                  ▼
   ┌─────────────────────────────┐
   │ Attach user to request ctx  │
   └─────────────────────────────┘


   Refresh flow with rotation
   ───────────────────────────
   POST /auth/refresh { refresh_token }
     │
     ▼
   Verify signature, exp, typ
     │
     ▼
   Look up session by sid
     │
     ├── if session.revoked_at IS NOT NULL
     │      → REUSE DETECTED
     │      → revoke whole family
     │      → bump users.token_version
     │      → log critical audit event
     │      → 401
     │
     └── if active
            → rotate: new refresh, same family
            → new access token
            → return both
```

---

## 7. Auto-approval caps and counters

```
   Policy caps:
   ┌───────────────────────────────┐
   │ global_per_day: 5000          │
   │ per_region_per_day: 500       │
   │ per_provider_per_day: 50      │
   │ per_service_type_per_day:1000 │
   │ per_requester_per_day: 3      │
   └───────────────┬───────────────┘
                   │
                   ▼
   Redis keys (day-bucketed, atomic INCR):
     idrm:cap:global:all:2026-10-12
     idrm:cap:region:{region_id}:2026-10-12
     idrm:cap:provider:{org_id}:2026-10-12
     idrm:cap:service:{type}:2026-10-12
     idrm:cap:req:{user_id}:2026-10-12

   Lua script:
     check all counters atomically
     if any >= its cap → return error
     else INCR all and return new values

   If Redis unavailable:
     Count from auto_approval_decisions
       WHERE decision='approved'
         AND policy_id = :policy
         AND evaluated_at >= date_trunc('day', now())
     Slower, but correct.
```

---

## 8. The two apps — request flow

```
   API request (public)
   ────────────────────
   Browser/Client
     │
     ▼ POST /api/v1/incidents
   ┌─────────────────────────┐
   │ FastAPI router          │
   │ - parse body            │
   │ - validate (Pydantic)   │
   │ - call service          │
   └────────────┬────────────┘
                │
                ▼
   ┌─────────────────────────┐
   │ Service layer           │
   │ - entity list check     │
   │ - INSERT incident       │
   │ - auto-approval         │
   │ - audit event           │
   └────────────┬────────────┘
                │
                ▼
   ┌─────────────────────────┐
   │ SQLAlchemy (async)      │
   │ asyncpg → PostgreSQL    │
   └────────────┬────────────┘
                │
                ▼
             JSON response


   Dashboard request (staff)
   ──────────────────────────
   Browser
     │
     ▼ GET /dashboard/dispatch
   ┌─────────────────────────┐
   │ Flask blueprint         │
   │ - session cookie check  │
   │ - permission check      │
   └────────────┬────────────┘
                │
                ▼
   ┌─────────────────────────┐
   │ Service (sync)          │
   │ - read queries          │
   │ - JOINs for display     │
   └────────────┬────────────┘
                │
                ▼
   ┌─────────────────────────┐
   │ SQLAlchemy (sync)       │
   │ psycopg2 → PostgreSQL   │
   └────────────┬────────────┘
                │
                ▼
             HTML response
```

---

## 9. Where to look when

| I want to understand… | Read |
|---|---|
| The big picture | Diagram 1 |
| Why there are two apps | Diagram 2 + ADR-0005 |
| Where a table lives | Diagram 3 |
| How incidents move | Diagram 4 |
| How auto-approval decides | Diagram 5 |
| How auth works | Diagram 6 |
| How caps prevent abuse | Diagram 7 |
| The shape of a request | Diagram 8 |
