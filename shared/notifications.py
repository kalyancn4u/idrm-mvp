"""
In-app notifications — building the rows.

A notification is one row in `notifications`; the API lists a user's rows at
`GET /notifications`. This module only BUILDS rows (no database access), so
the async API and the sync console can both use it: the caller adds the row
to its own session, and it is saved in the same transaction as the change it
reports.

Email / SMS delivery is not implemented; `notification_deliveries` stays empty.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from shared.enums import IncidentStatus, NotificationType
from shared.models.comms import Notification

# What the requester is told when their request changes state.
_STATUS_TEXT = {
    IncidentStatus.approved: "Your request was approved and is now visible to providers.",
    IncidentStatus.rejected: "Your request was not approved.",
    IncidentStatus.accepted: "A provider has taken up your request.",
    IncidentStatus.in_progress: "Help is on the way: work on your request has started.",
    IncidentStatus.completed: "The provider marked your request as done. Please confirm.",
    IncidentStatus.cancelled: "Your request was cancelled.",
}


def notification(
    *,
    user_id: uuid.UUID,
    type_: NotificationType,
    title: str,
    message: str,
    link: str | None = None,
) -> Notification:
    return Notification(
        user_id=user_id, type=type_, title=title[:255], message=message,
        link=link, is_read=False, created_at=datetime.now(UTC),
    )


def incident_status_changed(
    *,
    requester_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    incident_id: uuid.UUID,
    new_status: IncidentStatus,
    reason: str | None = None,
) -> Notification | None:
    """
    The row telling a requester their request moved, or None when nobody
    needs telling: a guest request (no account), a change the requester made
    themselves, or a state with nothing to say.
    """
    if requester_id is None or requester_id == actor_id:
        return None
    text = _STATUS_TEXT.get(new_status)
    if text is None:
        return None
    if reason and new_status in (IncidentStatus.rejected, IncidentStatus.cancelled):
        text = f"{text} Reason: {reason}"
    return notification(
        user_id=requester_id,
        type_=NotificationType.incident_update,
        title=f"Request {new_status.value.replace('_', ' ')}",
        message=text,
        link=f"/incidents/{incident_id}",
    )


def assigned_to_incident(*, user_id: uuid.UUID, incident_id: uuid.UUID) -> Notification:
    return notification(
        user_id=user_id,
        type_=NotificationType.assignment,
        title="You have been dispatched",
        message="A coordinator assigned you to a help request.",
        link=f"/incidents/{incident_id}",
    )
