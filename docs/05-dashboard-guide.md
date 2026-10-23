# Dashboard Guide

The staff console for coordinators and administrators.

## Who can log in

Only `coordinator` and `admin`. A citizen or provider cannot sign in — the
same "invalid credentials" error is returned regardless of reason.

## Layout

```
┌──────────────┬──────────────────────────────────────────────────┐
│              │  Topbar: breadcrumb · Dispatch · BigBoard · user │
│   Sidebar    ├──────────────────────────────────────────────────┤
│              │                                                  │
│   Overview   │                                                  │
│   Dispatch   │            Page content                          │
│   BigBoard   │                                                  │
│   Incidents  │                                                  │
│   Personnel  │                                                  │
│              │                                                  │
│  Coordination│                                                  │
│   Organizations                                                 │
│   Scheduling │                                                  │
│   Logistics  │                                                  │
│   Alerts     │                                                  │
│              │                                                  │
│  Governance  │                                                  │
│   Policies   │                                                  │
│   Decisions  │                                                  │
│   Entity Lists                                                  │
│   Audit      │                                                  │
│              │                                                  │
│  Admin       │                                                  │
│   Users      │                                                  │
│   Reports    │                                                  │
└──────────────┴──────────────────────────────────────────────────┘
```

## Overview

Five KPI cards:
- Open incidents + critical count
- Auto-approved requests
- Available personnel + units
- Organizations (verified count)
- Verified incidents

Plus: incidents by status, incidents by service, personnel status, unit
status, and recent activity.

## Dispatch Console — the crown jewel

`/dashboard/dispatch/`

The three-panel CAD workflow, inspired by Resgrid:

```
┌──────────────┬──────────────────────┬─────────────────┐
│              │                      │                 │
│   INCIDENT   │   INCIDENT DETAIL    │   AVAILABLE     │
│   QUEUE      │                      │   RESOURCES     │
│              │   - Description      │                 │
│   [Critical] │   - Priority         │   Personnel:    │
│   [High]     │   - Service type     │   ● Ravi        │
│   [Medium]   │   - Timeline         │   ● Anjali      │
│   [Low]      │                      │                 │
│              │   [Dispatch Now]     │   Units:        │
│   Click to   │   [Offer]            │   ● Food Truck  │
│   select     │                      │   ● Ambulance   │
└──────────────┴──────────────────────┴─────────────────┘
```

**How to use it:**

1. Click an incident in the left panel — it loads into the middle panel.
2. Click a resource chip in the right panel — it highlights and fills the
   hidden form field.
3. Add a note, then click **⚡ Dispatch Now** (immediate assignment) or
   **📨 Offer** (send to the resource; they must accept).

Both actions fire an audit event and update personnel/unit statuses.

## BigBoard — the wall display

`/dashboard/bigboard/`

The situational-awareness view designed for a wall-mounted screen. Auto-refreshes
every 30 seconds.

Widgets:
- **Active Incidents** — the open queue
- **Personnel Status** — counts by status
- **Unit Status** — counts by status
- **Organizations** — total, verified, available
- **Shift Coverage** — upcoming shifts and signup counts
- **Available Resources** — units and their current status

You can filter which widgets display by adding `?widget=active_incidents&widget=personnel_summary`
to the URL — useful for wall screens with limited space.

## Incidents

`/dashboard/incidents/`

Filter by status, service type, priority. Click through to a detail page
with a timeline and coordinator actions (Approve / Reject).

The dashboard drives only `approve` and `reject`. All other lifecycle
transitions happen through the public API.

## Personnel & Units

`/dashboard/personnel/`

Live operational status across the region — who is available, who is
responding, which units are in quarters.

## Organizations

`/dashboard/organizations/`

List of providers, with a **Verify** button on each row. Also a link to
**Pending Volunteers** — self-enrolled volunteers awaiting approval.

## Users

`/dashboard/users/`

Search by name or email, filter by role and status.

The user detail page has:
- **Role change** (admin only)
- **Status change** (admin only)
- **Active sessions** with a **Force sign-out** button

## Policies / Decisions / Entity Lists

**Policies** — every auto-approval rule. Toggle active/inactive.

**Decisions** — the complete decision log. Every auto-approval decision,
whether approved, deferred, or skipped, appears here with the counters at
decision time. When someone asks *"why did the system approve this?"*, this
is where you find the answer.

**Entity Lists** — blocklist/allowlist/watchlist management. Add an entry
with a value, list type, and effect. The engine enforces it on the next
request.

## Audit Trail

`/dashboard/audit/`

Filter by action and resource type. Every row shows the actor, IP, and a
JSON diff (`old_values` → `new_values`). The table is **append-only** — a
database trigger blocks UPDATE and DELETE.

## Reports

`/dashboard/reports/`

- Daily created / verified
- Average minutes to verify
- Top organizations

**⇩ Export CSV** — downloads `incidents.csv` and logs an EXPORT audit event.

## Shift handover routine

**Start of shift:**
1. Overview — glance at KPIs
2. Recent activity — what happened in the last few hours
3. Dispatch Console — clear the incident queue
4. BigBoard — check overall posture

**During shift:**
1. Dispatch Console — assign resources as incidents arrive
2. Alerts — issue area warnings
3. Organizations — verify new providers

**End of shift:**
1. Export incidents CSV for the log
2. Note the day's activity
3. Sign out — the session is invalidated
