# ADR-0016 — The Console's First Card Is the Triage Queue

**Status:** Accepted (2026-11-25). Code written, not yet run (the console has
not been started on this machine — PENDING-TASKS B-2).

**Builds on:** [ADR-0014](0014-approval-first.md) (approval first).

## Context

The first card on the staff console's overview page was labelled **Open
Incidents**. It counted requests in four states — `created`, `approved`,
`accepted`, `in_progress` — but its link opened the incident list filtered to
`created` only. A coordinator who saw "12" and clicked could land on a list
of 5, with no explanation (found while checking PENDING-TASKS H-5; recorded
as H-10).

Two fixes were possible: make the card count only what the link shows (the
requests waiting for approval), or teach the list to filter by several states
and keep counting all open work. The question put to the product owner was
which the card is for — triage, or overall load. The answer:

> Waiting for approval

## Decision

1. The first card is the coordinator's **triage queue**. It is labelled
   **Waiting for Approval** and counts requests in `created` (not deleted).
2. Its small line shows how many of those are **critical**.
3. Its link stays the incident list filtered to `created`, so the number and
   the list always agree.

## Consequences

- With approval first (ADR-0014), `created` is the pile a coordinator must
  act on; putting it first makes the console lead with the next action.
- Overall load (approved, accepted, in progress) no longer has its own card.
  It remains visible in the **Incidents by status** list on the same page.
- `dashboard/services/kpi.py` returns `incidents_awaiting_approval` and
  `incidents_awaiting_critical` instead of `incidents_open` and
  `incidents_critical`; only the overview template used the old names.

## Alternatives considered

**Keep "Open Incidents" and let the list filter by several states.** Rejected
by the owner's choice: it shows load rather than the next action, and needs a
change to the list filter as well as the card.
