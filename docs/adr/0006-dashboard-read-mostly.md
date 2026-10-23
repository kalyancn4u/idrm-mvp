# ADR-0006 — The Dashboard Is Read-Mostly

**Status:** Accepted

## Context

The staff console could expose every write action the API does. But that
would duplicate logic and widen the attack surface.

## Decision

The dashboard's write surface is deliberately small:

| Action | Route | Role |
|---|---|---|
| Approve incident | `POST /dashboard/incidents/<id>/approve` | coordinator |
| Reject incident | `POST /dashboard/incidents/<id>/reject` | coordinator |
| Verify organization | `POST /dashboard/organizations/<id>/verify` | coordinator |
| Unverify organization | `POST /dashboard/organizations/<id>/unverify` | coordinator |
| Approve volunteer | `POST /dashboard/organizations/volunteers/<id>/approve` | coordinator |
| Create alert | `POST /dashboard/alerts/new` | coordinator |
| Deactivate alert | `POST /dashboard/alerts/<id>/deactivate` | coordinator |
| Toggle policy | `POST /dashboard/policies/<id>/toggle` | admin |
| Add entity list entry | `POST /dashboard/policies/entity-lists` | coordinator |
| Change user role | `POST /dashboard/users/<id>/role` | admin |
| Change user status | `POST /dashboard/users/<id>/status` | admin |
| Force logout | `POST /dashboard/users/<id>/force-logout` | admin |

Everything else — accept, start, complete, verify an incident — is a
provider or citizen action through the public API.

## Consequences

- The dashboard's attack surface is small and auditable.
- Providers interact through the API only.
- Coordinators see what needs a human decision; the system handles the rest.
