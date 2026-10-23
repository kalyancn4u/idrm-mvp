# Demo Script — 10 Minutes

A narrative walkthrough for presenting IDRM to a stakeholder. Everything is
scripted; the story arc is: *problem → solution → proof*.

**Preparation:**

```bash
make db-reset   # clean slate
make seed       # fresh demo data
make run        # both apps up
```

Open two browser tabs:
1. `http://127.0.0.1:8000/docs` — API (cool slate)
2. `http://127.0.0.1:5000/dashboard/login` — Console (warm saffron)

---

## 0:00 — The problem (30 seconds)

Say:

> "During a flood, 500 people need help. Two things go wrong. First, nobody
> knows where everyone is. Second, nobody can prove who did what. IDRM fixes
> both. Watch."

---

## 0:30 — The two apps (1 minute)

Show the two browser tabs side by side.

Say:

> "There are two apps. On the left, the public API. Cool colours. JSON. This
> is what citizens and providers use. On the right, the staff console. Warm
> colours. Forms. This is what coordinators use. Same data, different views.
> The colour difference is not decorative — it tells the user which app they
> are in without a word."

Optionally: point out the URL bar — `:8000` vs `:5000`.

---

## 1:30 — A citizen raises a request (1 minute)

In the API tab, go to `/docs`, scroll to `POST /incidents`, click **Try it out**.

Paste this:

```json
{
  "service_type": "water",
  "priority": "medium",
  "description": "Demo — 40 families need drinking water in the Amberpet colony.",
  "location": {"latitude": 17.40, "longitude": 78.48}
}
```

Click **Execute**.

Point at the response:

> "The request has been created. Look at the status. It says **approved**.
> No coordinator touched it. The platform reviewed it automatically, and it
> will explain why in a moment."

---

## 2:30 — How auto-approval works (1 minute)

Open the console. Log in as `admin@idrm.local` / `Admin#2026`.

Navigate to **Decisions** (`/dashboard/policies/decisions`).

Point at the top row:

> "Every decision the platform makes is recorded. This row shows the request
> we just created. The decision is *approved*. The reason is *matched_policy*.
> The policy is `IN-TG-HYD-FOOD-WATER-LOW`. And here, in the counters column,
> is the state of the caps at the moment of the decision."

Click **view** on the JSON diff.

> "This is what the system knew when it made the decision. There is no
> black box. Every auto-approval is auditable."

---

## 3:30 — The Dispatch Console (2 minutes)

Navigate to **Dispatch** (`/dashboard/dispatch`).

Say:

> "This is the coordinator's view. Three panels. Left: what needs help.
> Middle: what you selected. Right: who can help."

Click the demo incident on the left.

The middle panel loads its details.

Click a resource chip on the right — for example, **Food Truck 01**.

It highlights. The form fields populate.

Say:

> "The coordinator picks a resource and clicks dispatch. The unit status
> changes, the assignment is logged, and the citizen is notified."

Click **⚡ Dispatch Now**.

Refresh the page. The unit now shows status **dispatched**.

---

## 5:30 — The BigBoard (1 minute)

Navigate to **BigBoard** (`/dashboard/bigboard`).

Say:

> "This is the wall display. Put this on a screen in the operations center.
> Six widgets. It refreshes every 30 seconds."

Point at each widget:

> "Active incidents. Personnel status. Unit status. Organizations. Shift
> coverage. Available resources."

---

## 6:30 — The audit trail (2 minutes)

Navigate to **Audit Trail** (`/dashboard/audit`).

Say:

> "Every action has been recorded. Every create, every dispatch, every
> login, every policy decision. Nothing is left out."

Filter by `resource_type = incident`. Two rows appear — the citizen's
create and the system's auto-approval.

Click **view** on either. The JSON diff appears.

Say:

> "This table is append-only. You cannot edit it. Let me show you."

Open a terminal:

```bash
make psql
```

```sql
UPDATE audit_logs SET action = 'tampered' WHERE id = (SELECT id FROM audit_logs LIMIT 1);
```

The terminal shows:

```
ERROR:  audit_logs is append-only — UPDATE and DELETE are forbidden
```

Say:

> "Not the app. Not a DBA. Not a rogue script. Nobody can alter this."

---

## 8:30 — The two-canvas distinction (30 seconds)

Scroll back to the two browser tabs.

Say:

> "This is the whole idea in one image. Cool colours for the public API.
> Warm colours for the staff console. Same data. Different audiences.
> Different responsibilities."

---

## 9:00 — What this proves (1 minute)

Say:

> "Three things. **First**, a citizen can ask for help in seconds without
> an account. **Second**, a coordinator has one screen with all the context
> they need. **Third**, every decision — human or machine — is permanently
> recorded. That is what makes this usable in a real disaster."

---

## 9:30 — Where to look next (30 seconds)

Say:

> "Everything is documented. Read `docs/01-getting-started.md` to run it
> yourself. Read `docs/12-governance.md` to understand the auto-approval.
> Read `docs/13-auth-and-sessions.md` to understand the security. And read
> `docs/adr/` for the *why* behind every architectural choice."

---

## 10:00 — End.

Take questions.

---

## Contingency plans

If something breaks during the demo:

| Broken | Fallback |
|---|---|
| API is down | Use the OpenAPI docs at `/docs` — they render from the app's metadata, which is cached |
| Database is down | Show the docs, not the app. `docs/DIAGRAMS.md` has every architecture picture |
| A specific endpoint 500s | Try a different incident. There are 12 seeded |
| The console login fails | Use the other coordinator account |
| The auto-approval doesn't fire | Open Decisions — even a `deferred` decision proves the engine ran |

---

## The three sentences to remember

If you remember nothing else, remember these:

1. **"Two apps, one database."**
2. **"Auto-approval is data-driven, not code-driven."**
3. **"The audit trail is provably append-only."**

Everything in the demo is an illustration of one of those three.
