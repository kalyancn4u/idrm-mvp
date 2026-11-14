# Seed Reference

What `make seed` creates (development only — it refuses to run with
`APP_ENV=production`; use `make seed-reference` there, which creates the
regions and nothing else). Reference this whenever you wonder "what is this
row?" or "where did this data come from?"

---

## Users

| Email | Name | Role | Language |
|---|---|---|---|
| `admin@idrm.local` | Platform Administrator | admin | en |
| `coord.hyd@idrm.local` | Anjali Rao | coordinator | en |
| `coord.vja@idrm.local` | Kiran Reddy | coordinator | te |
| `priya.citizen@example.com` | Priya Sharma | citizen | hi |
| `mohan.citizen@example.com` | Mohan Kumar | citizen | te |
| `sneha.citizen@example.com` | Sneha Iyer | citizen | en |
| `smilinghearts@ngo.example` | Smiling Hearts Foundation | provider | en |
| `apmedical@org.example` | AP Medical Response | provider | te |
| `volunteer.ravi@example.com` | Ravi Teja | provider | te |
| `volunteer.fatima@example.com` | Fatima Khan | provider | hi |

**Password:** all seeded users have `IDRMseed#2026` except `admin@idrm.local`,
which has `Admin#2026`.

---

## Regions

| Code | Name | Center (approximate) |
|---|---|---|
| `IN-TG-HYD` | Hyderabad Urban | 17.40 °N, 78.48 °E |
| `IN-AP-VJA` | Vijayawada Urban | 16.51 °N, 80.65 °E |
| `IN-AP-VTZ` | Visakhapatnam Urban | 17.68 °N, 83.22 °E |

The polygons are rectangles. They are simplified for the demo — real
boundaries would come from government shapefiles.

---

## Organizations

| Name | Type | Services | Center |
|---|---|---|---|
| Smiling Hearts Foundation | ngo | food, water | 17.38 °N, 78.48 °E |
| AP Medical Response | hospital | medical, rescue | 16.51 °N, 80.65 °E |

Both are verified.

---

## Units

| Name | Kind | Callsign | Status |
|---|---|---|---|
| Food Truck 01 | vehicle | FT-01 | in_quarters |
| Ambulance 07 | ambulance | AMB-07 | in_quarters |

---

## Personnel statuses

| User | Status |
|---|---|
| Ravi Teja (volunteer) | available |
| Fatima Khan (volunteer) | off_duty |
| Smiling Hearts Foundation | available |
| AP Medical Response | responding |

---

## Auto-approval policies

| Code | Applies to | Priority | Region | Services | Priority | Caps |
|---|---|---|---|---|---|---|
| `IN-TG-HYD-FOOD-WATER-LOW` | incident | 10 | HYD | food, water | low, medium | 500/day per region |
| `IN-AP-VJA-FOOD-WATER-LOW` | incident | 10 | VJA | food, water | low, medium | 300/day per region |
| `AUTO-VERIFY-NGO-LOW-RISK` | provider | 20 | all | food, water, shelter | — | 20/day per region (stored only: provider policies are not evaluated yet) |
| `REGION-BLACKOUT-VJA` | incident | 1 | VJA | (all) | (all) | inactive by default |

**The blackout policy is the kill switch.** Activate it from
`/dashboard/policies` to immediately stop all auto-approval in Vijayawada.

---

## Entity lists

| Entity | Value | List type | Effect | Reason |
|---|---|---|---|---|
| email | `spam@bad.example` | blocklist | hard_block | Confirmed spam requests |
| ip_address | `203.0.113.42` | watchlist | observe | Multiple failed logins |

---

## Incidents

| # | Service | Priority | Status | Region | Auto-approved |
|---|---|---|---|---|---|
| 1 | water | medium | approved | HYD | yes |
| 2 | food | low | approved | HYD | yes |
| 3 | medical | critical | created | HYD | no |
| 4 | rescue | high | accepted | VJA | no |

Incident 4 is assigned to AP Medical Response.

---

## Volunteering

| User | Scope | Status |
|---|---|---|
| Ravi Teja | Smiling Hearts | active |
| Fatima Khan | Smiling Hearts | pending |

Fatima's enrollment appears in `/dashboard/organizations/volunteers/pending`.

---

## What each row is good for

| Want to test | Look at |
|---|---|
| A pending coordinator decision | Incident 3 (medical, critical, created) |
| A dispatched unit | Incident 4 (accepted, assigned to AP Medical) |
| Auto-approval in action | Create a new food/water request in HYD |
| A blocked email | Add a list entry for a signed-in citizen's email, then create a help request as them (lists are checked at request creation, not at registration) |
| A watched IP | Listed for display only — IP entries are not enforced yet |
| Volunteer approval flow | Approve Fatima in the console |
| Policy kill switch | Activate `REGION-BLACKOUT-VJA` |

---

## Re-seeding

`make seed` is idempotent. Running it twice does nothing the second time.
To get a truly fresh state:

```bash
make db-reset     # drops everything, re-applies migrations, re-seeds
```

The seed uses **stable UUIDs** so re-running is a no-op. If you modify a
seed row, the change is not applied by re-running `make seed` — you must
`make db-reset` first.

---

## Extending the seed

The seed lives in `scripts/seed.py`. To add a row:

1. Define a stable UUID for the row (see the constants at the top).
2. Add an `_upsert_*` call in the `main()` function.
3. Run `make db-reset` in dev to apply.

`sql/06_sample_data.sql` contains a mirror of the same data for DBAs who
prefer SQL. Keep the two in sync.
