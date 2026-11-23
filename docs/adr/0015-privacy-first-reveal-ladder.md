# ADR-0015 — Privacy First: Hide Personal Data by Default, Reveal It by Need

**Status:** Accepted (2026-11-24). Not yet built — see `docs/review/PENDING-TASKS.md` Part G.

**Design:** [PRIVACY-FIRST-DATA-DESIGN.md](../design/PRIVACY-FIRST-DATA-DESIGN.md)
holds the full reasoning, the reveal ladder (§7) and the mechanisms (§8).
This ADR records only the choices the owner made.

**Refines:** [ADR-0014](0014-approval-first.md) (approval first) — this ADR
extends "a provider may claim only an approved request" to "a provider may
*see* only an approved request".

## Context

A help request holds very personal data: where someone is, their phone
number, their health. Reading the code on 2026-11-24 found that it shows too
much and too little at once:

- every provider sees every request, including unapproved ones, with the
  exact location, the requester's id and the guest's tracking token;
- yet the assigned provider has no way to get the citizen's phone number.

The MVP security spec already promises that citizen contact is "shared with
an assigned provider only as needed" and names India's DPDP Act 2023. Seven
questions about how far to go were put to the product owner, each with a
recommended default (design §16). The owner's answer:

> Adopt defaults

## Decision

The rule is: **hide by default, reveal by need, never let hiding block a
rescue.** Specifically:

| # | Question | Decision |
|---|---|---|
| D1 | May providers see requests that are not yet approved? | **No.** Providers see a request only once it is `approved`. |
| D2 | How does an assigned provider get the phone number? | **A one-tap reveal, recorded.** Each reveal writes a `pii_reveals` row and a `pii.revealed` audit row (without the number). |
| D3 | How rough is the location while a provider is browsing? | **Snapped to a 0.01° grid (~1 km) in urban regions, 0.05° (~5 km) in regions marked rural.** Exact location only after assignment. |
| D4 | How long are contact details kept after a request closes? | **30 days**, then deleted. Exact location is coarsened at the same time. |
| D5 | May admins see case details? | **Only through break-glass** (reason recorded, reviewed afterwards). Admins run the platform, not rescues. |
| D6 | Legal basis for life-safety requests | **DPDP "legitimate use"**; the privacy notice is still shown and recorded. **Must be confirmed by legal counsel before launch.** |
| D7 | How long does the assignee keep access after the request ends? | **72 hours**, then back to the coarse view. |

## Consequences

- One new Alembic revision adds `incident_contacts`, `pii_reveals`,
  `consent_records` and new `incidents` columns (design §9). `guest_contact`
  and `tracking_token` move or become hashed.
- All incident output goes through one function, `shared/privacy.py`
  `shape_incident`, used by both the API and the console.
- Regions need an urban/rural marker for D3.
- A daily retention job becomes part of operations.
- The console gets a reveal button and a break-glass review list.
- Admins lose the case-detail access they have in today's code.
- D6 is a legal question; launch waits on counsel's answer.

## Alternatives considered

Each question's other options, and why they were not chosen, are in design
§16 and §15: showing unapproved requests coarsely (exposes unvetted reports),
showing the phone automatically on assignment (no record of who looked),
in-app chat only (fails on poor networks), one cell size everywhere
(identifies rural homes or is useless in cities), 7- or 90-day retention, and
consent on every request (adds a step for people in danger).
