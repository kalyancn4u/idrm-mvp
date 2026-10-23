# ADR-0012 — Volunteer Enrollment Is Scope-Based

**Status:** Accepted

## Context

A volunteer might contribute to a specific organization, a specific event,
a region, or a service type. A `role` alone cannot express this. Two
accounts per person is unacceptable UX.

## Decision

A volunteer is a `user` with the `provider` role and one or more rows in
`volunteer_enrollments`. Each enrollment has:

- `scope_type` — `organization`, `event`, `region`, `service`
- `scope_id` — the specific scope
- `status` — `pending`, `active`, `suspended`, `completed`, `rejected`
- `self_enrolled_at`, `approved_by`, `approved_at`

Approval is by a coordinator of the same scope. `organization_members`
grants that privilege; `user_delegations` extends it further.

## Consequences

- One user can volunteer for multiple scopes without multiple accounts.
- Approval rights are scoped, not global.
- The dashboard has a **Pending Volunteers** page for coordinators.
- The API has `POST /volunteers/enroll` and `GET /volunteers/mine`.
