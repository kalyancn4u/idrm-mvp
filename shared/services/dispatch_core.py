"""
Dispatch rules — the part that is the same for both apps.

The API talks to the database asynchronously and the staff console
synchronously, so each needs its own thin service to load and save rows
(`shared/services/dispatch.py` and `dashboard/services/dispatch.py`).
Everything that is a *decision* lives here instead, as plain functions that
touch no database: what an assignment looks like, which status a unit moves
to, when an offer may still be answered. Written once, the two apps cannot
drift apart.

Each function takes rows that the caller has already loaded, changes them or
builds new ones, and returns what the caller must add to its session.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from shared.enums import DispatchOfferStatus, PersonnelStatus, UnitStatus
from shared.models.dispatch import DispatchAssignment, DispatchOffer
from shared.models.personnel import (
    PersonnelStatusEvent,
    PersonnelStatusRow,
    UnitStatusEvent,
    UnitStatusRow,
)

# What dispatching and releasing do to a unit / person.
UNIT_WHEN_ASSIGNED = UnitStatus.dispatched
PERSON_WHEN_ASSIGNED = PersonnelStatus.responding
UNIT_WHEN_RELEASED = UnitStatus.in_quarters
PERSON_WHEN_RELEASED = PersonnelStatus.available

DEFAULT_OFFER_TTL_MINUTES = 15


class OfferError(ValueError):
    """The offer cannot be answered. `str(error)` is safe to show the user."""


def new_assignment(
    *,
    incident_id: uuid.UUID,
    unit_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    actor_id: uuid.UUID,
    note: str | None,
    now: datetime,
) -> DispatchAssignment:
    return DispatchAssignment(
        incident_id=incident_id,
        unit_id=unit_id,
        user_id=user_id,
        assigned_by=actor_id,
        assigned_at=now,
        note=note,
    )


def new_offer(
    *,
    incident_id: uuid.UUID,
    unit_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    actor_id: uuid.UUID,
    now: datetime,
    ttl_minutes: int = DEFAULT_OFFER_TTL_MINUTES,
    note: str | None = None,
) -> DispatchOffer:
    return DispatchOffer(
        incident_id=incident_id,
        unit_id=unit_id,
        user_id=user_id,
        offered_by=actor_id,
        offered_at=now,
        expires_at=now + timedelta(minutes=ttl_minutes),
        note=note,
    )


def change_unit_status(
    current: UnitStatusRow | None,
    *,
    unit_id: uuid.UUID,
    status: UnitStatus,
    actor_id: uuid.UUID | None,
    incident_id: uuid.UUID | None,
    note: str | None,
    now: datetime,
) -> tuple[UnitStatusRow, UnitStatusEvent, bool]:
    """
    Move a unit to `status`.

    Returns `(row, event, is_new)`: the current-status row (created if the
    unit had none), the history event to add, and whether the row is new and
    so must be added to the session too.
    """
    is_new = current is None
    row = current or UnitStatusRow(unit_id=unit_id)
    previous = row.status
    row.status = status
    row.incident_id = incident_id
    row.note = note
    row.updated_at = now
    event = UnitStatusEvent(
        unit_id=unit_id,
        from_status=previous,
        to_status=status,
        incident_id=incident_id,
        note=note,
        actor_id=actor_id,
        occurred_at=now,
    )
    return row, event, is_new


def change_personnel_status(
    current: PersonnelStatusRow | None,
    *,
    user_id: uuid.UUID,
    status: PersonnelStatus,
    incident_id: uuid.UUID | None,
    note: str | None,
    now: datetime,
) -> tuple[PersonnelStatusRow, PersonnelStatusEvent, bool]:
    """Move a person to `status`. Same return shape as `change_unit_status`."""
    is_new = current is None
    row = current or PersonnelStatusRow(user_id=user_id)
    previous = row.status
    row.status = status
    row.note = note
    row.updated_at = now
    event = PersonnelStatusEvent(
        user_id=user_id,
        from_status=previous,
        to_status=status,
        note=note,
        incident_id=incident_id,
        occurred_at=now,
    )
    return row, event, is_new


def resolve_offer(offer: DispatchOffer | None, *, accept: bool, now: datetime) -> None:
    """
    Record the answer to an offer, or raise `OfferError`.

    An offer past its `expires_at` is marked `expired` before the error is
    raised — the caller should save that change even though the answer failed.
    """
    if offer is None or offer.status != DispatchOfferStatus.pending:
        raise OfferError("Offer not found or already resolved")
    if offer.expires_at and offer.expires_at < now:
        offer.status = DispatchOfferStatus.expired
        raise OfferError("Offer has expired")
    offer.status = DispatchOfferStatus.accepted if accept else DispatchOfferStatus.declined
    offer.responded_at = now


def close_assignment(assignment: DispatchAssignment | None, *, now: datetime) -> bool:
    """Mark an assignment released. False if there is nothing to release."""
    if assignment is None or assignment.released_at is not None:
        return False
    assignment.released_at = now
    return True
