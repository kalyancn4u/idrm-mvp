# ADR-0014 — Approval Comes First; Auto-Approval Is a Coordinator's Time-Boxed Regional Switch

**Status:** Accepted (2026-11-14)

**Refines:** [ADR-0007](0007-auto-approval.md) (auto-approval is policy-driven).
ADR-0007 still describes *how* the engine works. This ADR records *who may
switch it on, for where, for how long, and what happens when nobody does*.

## Context

A help request (an "incident") starts in the state `created`. A provider
claims it with the `accept` action.

The code let a provider claim a request straight from `created`, before any
coordinator had looked at it. The README's lifecycle picture said the
opposite: approval first, then claim. The two disagreed (item D-035 in
`docs/review/DISCREPANCY-REGISTER.md`), so the question was put to the
product owner:

> Should a provider be allowed to claim a request before a coordinator
> approves it?

The answer, in the owner's words:

> For some time of disaster events, in a specific geo region and for a
> stipulated amount of time — auto-approval can be set by the co-ordinator.
>
> If not set, then, the default is, require approval.

## Decision

1. **The default is: approval is required.** A provider can `accept` a
   request only when it is `approved`. A request in `created` cannot be
   claimed.

2. **A request becomes `approved` in exactly two ways:**
   - a coordinator (or admin) approves it by hand; or
   - an auto-approval policy that is in force *for that region at that
     moment* matches it when it is created.

3. **A coordinator may switch auto-approval on for a disaster**, by creating
   a policy that is limited in both space and time:
   - it applies to help requests (`applies_to = incident`);
   - it names at least one region (`region_scope`);
   - it has an end time (`effective_to`).

   A start time (`effective_from`) is optional; without one the policy starts
   immediately.

4. **When the end time passes, the policy stops on its own.** Nobody has to
   remember to turn it off. New requests in that region go back to waiting
   for a coordinator — that is, back to the default in point 1.

5. **Anything wider stays with an admin.** A policy with no region (the whole
   platform) or no end time (open-ended) can be created only by an admin. A
   coordinator can switch a region-scoped policy on or off in the console,
   but not a platform-wide one.

In one picture:

```
                        is an auto-approval policy in force
                        for this region, right now?
                                     │
                  ┌──────── no ──────┴────── yes ───────┐
                  ▼                                      ▼
   created ── waits for a coordinator ──▶ approved ◀── approved by the system
                                             │
                                          accept   (provider claims)
                                             ▼
                                          accepted ─▶ in_progress ─▶ completed ─▶ verified
```

### Who may do what

| Action | citizen | provider | coordinator | admin |
|---|:-:|:-:|:-:|:-:|
| Claim a request that is `created` | — | ❌ | — | — |
| Claim a request that is `approved` | — | ✅ | — | — |
| Approve a request by hand | ❌ | ❌ | ✅ | ✅ |
| Create a policy with a region **and** an end time | ❌ | ❌ | ✅ | ✅ |
| Create a platform-wide or open-ended policy | ❌ | ❌ | ❌ | ✅ |
| Switch a region-scoped policy on / off | ❌ | ❌ | ✅ | ✅ |
| Switch a platform-wide policy on / off | ❌ | ❌ | ❌ | ✅ |

### Where it lives in the code

| Rule | File |
|---|---|
| `accept` only from `approved` | `shared/lifecycle.py` — `TRANSITIONS["accept"]` |
| Coordinator limits on policy creation | `app/modules/policies/router.py` — `create_policy` |
| Policy ignored outside its period | `shared/governance/evaluator.py` — `_load_policies` |
| Region must match | `shared/governance/evaluator.py` — `_matches_scope` |
| Console: who may toggle which policy | `dashboard/blueprints/policies.py` — `toggle`; `dashboard/security.py` |
| Test for the default | `tests/unit/test_lifecycle.py` |

How to use it, with a worked example, is in
[12-governance.md](../12-governance.md#approval-comes-first).

## Consequences

- **Safe by default.** With no policy, or after one expires, every request
  is seen by a coordinator before a provider can act on it.
- **Fast when it matters.** During a named event the coordinator on the
  ground can remove the approval bottleneck for the affected area without
  waiting for an admin.
- **Self-cleaning.** Because an end time is mandatory for coordinators, an
  emergency setting cannot be left on by accident.
- **Auditable.** Creating a policy writes a `policy.created` audit row with
  the regions and the period; every decision the engine makes is a row in
  `auto_approval_decisions`.
- **A behaviour change for providers.** A client that used to call `accept`
  on a `created` request now gets `409 invalid_transition`. It must wait for
  `approved`.
- **Other limits still apply.** A coordinator's policy is still subject to
  its caps, its service-type and priority filters, and the platform kill
  switch `AUTO_APPROVAL_ENABLED`.

## Known gaps

These are stated so nobody assumes more than is built:

- **There is no "disaster event" record.** The system has no table for an
  event such as "Hyderabad floods, November 2026". A policy is tied to a
  *region* and a *period*; the event exists only in the policy's name. If
  events become first-class later, a policy should reference one.
- **No maximum period is enforced.** A coordinator must give an end time,
  but may set it far in the future. A ceiling (for example 30 days) is a
  product decision that has not been made.
- **A coordinator is not tied to a region.** Any coordinator may create a
  policy for any region. Restricting a coordinator to "their" region needs a
  coordinator-to-region link that does not exist yet.
- **No console form.** A coordinator creates the policy through the API
  (`POST /api/v1/policies`). The console can only switch an existing policy
  on or off.
- **The `assign` action is unchanged.** A coordinator directly assigning a
  `created` request to an organization is itself a coordinator decision, so
  it is still allowed without a separate approve step.

## Alternatives considered

- **Let providers claim `created` requests (the old behaviour).** Rejected:
  it makes approval optional everywhere, all the time, which is the opposite
  of the stated default.
- **Admin-only policy creation (the old behaviour).** Rejected: during a
  disaster the person who knows the area needs relief is the coordinator;
  routing through an admin adds delay exactly when speed matters.
- **Let coordinators create any policy.** Rejected: an open-ended or
  platform-wide auto-approval is a standing change to how the platform
  works, not an emergency measure.
- **A per-region on/off flag instead of a policy.** Rejected: a flag has no
  end time, no caps and no service-type or priority filter; the policy row
  already carries all of these (ADR-0007).
