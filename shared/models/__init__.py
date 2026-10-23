"""
Single import point for every ORM model.

Both apps import from here so there is exactly one SQLAlchemy metadata
registry. Import order matters only for the mapper configuration pass —
SQLAlchemy resolves strings lazily.
"""

from shared.models.alert import Alert
from shared.models.audit import AuditLog
from shared.models.base import Base, SoftDelete, Timestamps, UUIDPrimaryKey
from shared.models.comms import (
    ChatChannel,
    ChatMessage,
    Message,
    Notification,
    NotificationDelivery,
    NotificationPreference,
)
from shared.models.dispatch import DispatchAssignment, DispatchOffer
from shared.models.file import File
from shared.models.governance import (
    AutoApprovalDecision,
    AutoApprovalPolicy,
    BigboardConfig,
    BigboardWidget,
    EntityList,
    EntityListMatch,
    MutualAidAgreement,
    RateLimitEvent,
    Region,
)
from shared.models.ics import (
    IncidentCommand,
    IncidentLane,
    LaneAssignment,
    RunLog,
    RunLogEntry,
)
from shared.models.identity import (
    EmailVerificationToken,
    LoginAttempt,
    PasswordHistory,
    PasswordResetToken,
    User,
    UserSession,
)
from shared.models.incident import Incident, IncidentUpdate
from shared.models.logistics import (
    InventoryItem,
    InventoryLocation,
    InventoryTransaction,
)
from shared.models.organization import (
    Organization,
    OrganizationMember,
    Resource,
    UserDelegation,
    VolunteerEnrollment,
)
from shared.models.personnel import (
    PersonnelStatusEvent,
    PersonnelStatusRow,
    Unit,
    UnitMember,
    UnitStatusEvent,
    UnitStatusRow,
)
from shared.models.scheduling import (
    CalendarEvent,
    Certification,
    EventRSVP,
    Shift,
    ShiftSignup,
    ShiftTrade,
    Training,
    TrainingAssignment,
    TrainingCompletion,
)

__all__ = [
    "Alert", "AuditLog", "Base", "BigboardConfig", "BigboardWidget",
    "CalendarEvent", "Certification", "ChatChannel", "ChatMessage",
    "DispatchAssignment", "DispatchOffer", "EmailVerificationToken",
    "EntityList", "EntityListMatch", "EventRSVP", "File", "Incident",
    "IncidentCommand", "IncidentLane", "IncidentUpdate", "InventoryItem",
    "InventoryLocation", "InventoryTransaction", "LaneAssignment",
    "LoginAttempt", "Message", "MutualAidAgreement", "Notification",
    "NotificationDelivery", "NotificationPreference", "Organization",
    "OrganizationMember", "PasswordHistory", "PasswordResetToken",
    "PersonnelStatusEvent", "PersonnelStatusRow", "RateLimitEvent",
    "Region", "Resource", "RunLog", "RunLogEntry", "Shift", "ShiftSignup",
    "ShiftTrade", "SoftDelete", "Timestamps", "Training",
    "TrainingAssignment", "TrainingCompletion", "Unit", "UnitMember",
    "UnitStatusEvent", "UnitStatusRow", "User", "UserDelegation",
    "UserSession", "UUIDPrimaryKey", "VolunteerEnrollment",
    "AutoApprovalDecision", "AutoApprovalPolicy",
]
