# Tutorial — Your First End-to-End Workflow

A hands-on walkthrough. Read this after `docs/01-getting-started.md`. You
will raise a request, watch it auto-approve, dispatch a unit, and verify
the audit trail. Total time: **30 minutes**.

---

## Prerequisites

```bash
make setup        # venv + install + keys + infra + db + migrate + seed
make run          # API :8000, Dashboard :5000
```

Two terminals are more comfortable: run `make run` in one and use the other
for curl commands.

---

## Chapter 1 — See the platform

Open two browser tabs:

- **API**: http://127.0.0.1:8000/docs
- **Console**: http://127.0.0.1:5000/dashboard/login

Notice the difference: the API is on a **cool slate** background; the console
is on a **warm saffron** one. This is not decoration — it tells you which app
you are looking at without reading a word.

Sign into the console as:

```
Email:    admin@idrm.local
Password: Admin#2026
```

You should land on the **Overview** page. Four KPI cards, several charts,
recent activity.

---

## Chapter 2 — Register as a citizen (API)

In your terminal:

```bash
API=http://127.0.0.1:8000/api/v1

curl -s -X POST $API/auth/register \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "tutorial@example.com",
    "password": "TutorialPass#1",
    "name": "Tutorial User",
    "role": "citizen",
    "language": "en"
  }' | jq
```

**Expected output:**

```json
{
  "user": {
    "id": "…",
    "email": "tutorial@example.com",
    "name": "Tutorial User",
    "role": "citizen",
    "status": "active"
  }
}
```

The account is active immediately (MVP shortcut — email verification is
deferred to the FFP).

---

## Chapter 3 — Log in and capture a token

```bash
TOKENS=$(curl -s -X POST $API/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"tutorial@example.com","password":"TutorialPass#1"}')

ACCESS=$(echo $TOKENS | jq -r '.tokens.access_token')
REFRESH=$(echo $TOKENS | jq -r '.tokens.refresh_token')

echo "Access  : ${ACCESS:0:40}…"
echo "Refresh : ${REFRESH:0:40}…"
```

**What just happened:**

The API issued **two tokens**:
- A short-lived **access token** (~120 minutes for a citizen, with ±20 min jitter).
- A long-lived **refresh token** (~180 days).

Every subsequent request carries the access token. When it expires, the
refresh token mints a new one — the client does not need to re-login.

---

## Chapter 4 — Raise an incident (that will auto-approve)

The seed loaded a policy called `IN-TG-HYD-FOOD-WATER-LOW` — it auto-approves
low-priority food and water requests inside Hyderabad, up to 500 per day.

Send a request that matches:

```bash
INCIDENT=$(curl -s -X POST $API/incidents \
  -H "Authorization: Bearer $ACCESS" \
  -H 'Content-Type: application/json' \
  -d '{
    "service_type": "water",
    "priority": "medium",
    "description": "Tutorial test — 5 families need drinking water near the Amberpet colony.",
    "location": {"latitude": 17.40, "longitude": 78.48}
  }')

echo $INCIDENT | jq
```

**Expected output (abridged):**

```json
{
  "id": "…",
  "service_type": "water",
  "priority": "medium",
  "status": "approved",
  "auto_approved": true,
  "description": "Tutorial test — 5 families…",
  "latitude": 17.40,
  "longitude": 78.48
}
```

**Look at `"status": "approved"`.** No coordinator touched this request. The
governance engine:
1. Found the request's region (Hyderabad) via PostGIS `ST_Covers`.
2. Loaded the active policies for `applies_to = "incident"`.
3. Matched `IN-TG-HYD-FOOD-WATER-LOW` by region, service type, and priority.
4. Checked the daily cap counters (atomic via Redis).
5. Recorded the decision in `auto_approval_decisions`.
6. Moved the incident straight to `approved`.

**If you got `status: "created"` instead:** the policy was not loaded, or
the caps were exhausted, or the coordinates were outside Hyderabad. Check
`/dashboard/policies` in the console to see the active policies.

---

## Chapter 5 — See it in the console

Go back to the console and open:

**Incidents** → the new request is at the top, with an `auto` badge.

Click it to see:
- The status is **approved** (not created).
- The timeline shows two entries: `created` and `auto-approved`.

**Decisions** (`/dashboard/policies/decisions`):

The most recent row is your incident. Columns: `When`, `Subject`,
`Decision=approved`, `Reason=matched_policy`, `Policy=IN-TG-HYD-FOOD-WATER-LOW`,
`Counters` showing the values at decision time.

This is the "prove it" view — when someone asks *"why did the system approve
this?"*, you show them this row.

---

## Chapter 6 — See it in the audit trail

Open **Audit Trail** (`/dashboard/audit`).

Filter by `resource_type = incident`. You will see:

1. `incident.created` — actor is your tutorial user.
2. `incident.auto_approved` — actor is `null` (system).

Click **view** on either row to see the JSON diff. This is the complete
history, permanently recorded.

**Prove the table is immutable.** In another terminal:

```bash
make psql

-- Inside psql:
UPDATE audit_logs SET action = 'tampered'
 WHERE id = (SELECT id FROM audit_logs LIMIT 1);
```

**Expected output:**

```
ERROR:  audit_logs is append-only — UPDATE and DELETE are forbidden
```

The trigger worked. No app, no DBA, no script can alter the trail.

Type `\q` to exit psql.

---

## Chapter 7 — Dispatch it (as a coordinator)

Log out of the console. Log in as:

```
Email:    coord.hyd@idrm.local
Password: IDRMseed#2026
```

Open the **Dispatch Console** (`/dashboard/dispatch`).

Three panels:

- **Left** — the incident queue (your tutorial request is near the top).
- **Middle** — detail for the selected incident.
- **Right** — available resources: personnel and units.

Click your tutorial incident on the left. The middle panel loads its details.

Now click a resource chip on the right — for example, the **Food Truck 01**
unit. It highlights. The hidden form fields are now populated.

Optional: add a note ("Test dispatch — ETA 5 min").

Click **⚡ Dispatch Now**.

**What just happened:**

1. A `dispatch_assignments` row was created.
2. The unit's status changed to `dispatched`.
3. The unit's status event was recorded.
4. An audit event `dispatch.assigned` was logged.

Refresh the Dispatch Console. The unit now shows status `dispatched`.
The incident has an assigned organization.

---

## Chapter 8 — Verify the state changes were audited

Open **Audit Trail** again. Filter by `resource_type = dispatch_assignment`.

You should see `dispatch.assigned`. Click **view** — you can see the
`new_values` JSONB snapshot.

This is the whole story: every state change, in one table, with before and
after.

---

## Chapter 9 — Use the BigBoard

Open **BigBoard** (`/dashboard/bigboard`).

Six widgets: active incidents, personnel status, unit status, organizations,
shift coverage, available resources.

The BigBoard auto-refreshes every 30 seconds. This is the wall-display view —
what you would put on a screen in the emergency operations center.

---

## Chapter 10 — Try the refresh flow

Your access token will eventually expire. Here is how to refresh it:

```bash
NEW=$(curl -s -X POST $API/auth/refresh \
  -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"$REFRESH\"}")

NEW_ACCESS=$(echo $NEW | jq -r '.access_token')
NEW_REFRESH=$(echo $NEW | jq -r '.refresh_token')

echo "New access : ${NEW_ACCESS:0:40}…"
echo "New refresh: ${NEW_REFRESH:0:40}…"
```

**Look carefully:** both tokens changed. This is **refresh rotation** — the
API issued a new refresh token and invalidated the old one.

**Prove reuse detection.** Try to refresh again with the **old** refresh
token:

```bash
curl -s -X POST $API/auth/refresh \
  -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"$REFRESH\"}" | jq
```

**Expected output:**

```json
{
  "error": {
    "code": "invalid_token",
    "message": "Refresh token reuse detected."
  }
}
```

This is what happens when someone steals a refresh token and uses it — the
platform assumes theft, revokes the entire token family, and bumps the
user's `token_version` so every token issued before the theft is dead.

You can confirm this in the audit trail: `auth.refresh_reuse_detected`, at
**critical** severity.

---

## Chapter 11 — Reset

You have created a few rows. To go back to a clean state:

```bash
make db-reset     # asks for confirmation
make seed
```

The database is fresh again.

---

## What you have learned

| Concept | You saw it in |
|---|---|
| Two apps, one database | Chapters 1, 5 |
| Two-token JWT | Chapter 3 |
| Auto-approval from data-driven policies | Chapter 4 |
| Immutable audit trail | Chapters 6, 8 |
| The Dispatch Console | Chapter 7 |
| The BigBoard | Chapter 9 |
| Refresh rotation with reuse detection | Chapter 10 |

---

## Where to go next

- [Architecture](02-architecture.md) — why two apps
- [Data Model](03-data-model.md) — the 60 tables
- [Governance](12-governance.md) — how policies work
- [Auth & Sessions](13-auth-and-sessions.md) — the full auth design
- [Client Examples](CLIENT_EXAMPLES.md) — code in Python, JavaScript, and shell

