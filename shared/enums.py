"""Every domain enum, in one import-stable place."""

from __future__ import annotations

import enum


# ---- Identity ----------------------------------------------------------------
class UserRole(str, enum.Enum):
    citizen = "citizen"
    provider = "provider"
    coordinator = "coordinator"
    admin = "admin"


class UserStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    suspended = "suspended"
    deactivated = "deactivated"


# ---- Organization ------------------------------------------------------------
class OrgType(str, enum.Enum):
    ngo = "ngo"
    government = "government"
    private = "private"
    hospital = "hospital"
    volunteer_group = "volunteer_group"


class OrgMemberRole(str, enum.Enum):
    owner = "owner"
    coordinator = "coordinator"
    member = "member"


class EnrollmentScope(str, enum.Enum):
    organization = "organization"
    event = "event"
    region = "region"
    service = "service"


class EnrollmentStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    suspended = "suspended"
    completed = "completed"
    rejected = "rejected"


# ---- Incident ----------------------------------------------------------------
class ServiceType(str, enum.Enum):
    medical = "medical"
    food = "food"
    rescue = "rescue"
    water = "water"
    shelter = "shelter"
    other = "other"


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IncidentStatus(str, enum.Enum):
    created = "created"
    approved = "approved"
    accepted = "accepted"
    in_progress = "in_progress"
    completed = "completed"
    verified = "verified"
    cancelled = "cancelled"
    rejected = "rejected"


# ---- Alerts / notifications --------------------------------------------------
class AlertSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class NotificationType(str, enum.Enum):
    incident_update = "incident_update"
    assignment = "assignment"
    alert = "alert"
    verification = "verification"
    system = "system"


class DeliveryChannel(str, enum.Enum):
    email = "email"
    sms = "sms"
    in_app = "in_app"
    webhook = "webhook"


class DeliveryStatus(str, enum.Enum):
    queued = "queued"
    sent = "sent"
    failed = "failed"
    abandoned = "abandoned"


# ---- Files -------------------------------------------------------------------
class FilePurpose(str, enum.Enum):
    incident_photo = "incident_photo"
    completion_proof = "completion_proof"
    org_document = "org_document"
    training_material = "training_material"


# ---- Governance --------------------------------------------------------------
class AppliesTo(str, enum.Enum):
    incident = "incident"
    provider = "provider"


class DecisionKind(str, enum.Enum):
    approved = "approved"
    rejected = "rejected"
    deferred = "deferred"
    skipped = "skipped"


class DecisionReason(str, enum.Enum):
    matched_policy = "matched_policy"
    no_policy_matched = "no_policy_matched"
    cap_exceeded = "cap_exceeded"
    region_mismatch = "region_mismatch"
    disabled = "disabled"
    redis_unavailable = "redis_unavailable"
    invalid_policy = "invalid_policy"
    outside_known_region = "outside_known_region"
    entity_blocked = "entity_blocked"


class ListType(str, enum.Enum):
    blocklist = "blocklist"
    allowlist = "allowlist"
    watchlist = "watchlist"


class ListEffect(str, enum.Enum):
    hard_block = "hard_block"
    soft_block = "soft_block"
    allow_override = "allow_override"
    observe = "observe"


class EntityType(str, enum.Enum):
    user_id = "user_id"
    email = "email"
    phone = "phone"
    ip_address = "ip_address"
    device_fingerprint = "device_fingerprint"
    organization_id = "organization_id"
    region_id = "region_id"


class IdentityType(str, enum.Enum):
    user = "user"
    ip = "ip"
    session = "session"
    anonymous = "anonymous"


class LoginOutcome(str, enum.Enum):
    success = "success"
    bad_password = "bad_password"
    unknown_user = "unknown_user"
    locked = "locked"
    disabled = "disabled"
    blocked = "blocked"


# ---- Operations (Resgrid-inspired) ------------------------------------------
class PersonnelStatus(str, enum.Enum):
    available = "available"
    responding = "responding"
    on_scene = "on_scene"
    transporting = "transporting"
    at_hospital = "at_hospital"
    returning = "returning"
    unavailable = "unavailable"
    off_duty = "off_duty"


class UnitStatus(str, enum.Enum):
    in_quarters = "in_quarters"
    dispatched = "dispatched"
    en_route = "en_route"
    on_scene = "on_scene"
    transporting = "transporting"
    at_hospital = "at_hospital"
    returning = "returning"
    out_of_service = "out_of_service"
    unavailable = "unavailable"


class ShiftType(str, enum.Enum):
    assigned = "assigned"
    signup = "signup"


class TradeStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    cancelled = "cancelled"
    expired = "expired"


class CertificationStatus(str, enum.Enum):
    active = "active"
    expiring = "expiring"
    expired = "expired"
    revoked = "revoked"


class TrainingStatus(str, enum.Enum):
    assigned = "assigned"
    in_progress = "in_progress"
    completed = "completed"
    overdue = "overdue"
    expired = "expired"


class InventoryKind(str, enum.Enum):
    perishable = "perishable"
    durable = "durable"


class InventoryTxnType(str, enum.Enum):
    receipt = "receipt"
    issue = "issue"
    transfer = "transfer"
    adjustment = "adjustment"
    return_ = "return"
    disposal = "disposal"


class IcsLaneType(str, enum.Enum):
    division = "division"
    group = "group"
    branch = "branch"
    sector = "sector"
    strike_team = "strike_team"
    task_force = "task_force"
    staging = "staging"
    unified_command = "unified_command"


class IcsRole(str, enum.Enum):
    incident_commander = "incident_commander"
    operations = "operations"
    planning = "planning"
    logistics = "logistics"
    finance = "finance"
    safety = "safety"
    public_information = "public_information"
    liaison = "liaison"
    division_supervisor = "division_supervisor"
    group_supervisor = "group_supervisor"
    branch_director = "branch_director"
    strike_team_leader = "strike_team_leader"
    task_force_leader = "task_force_leader"
    staging_area_manager = "staging_area_manager"
    resource_unit_leader = "resource_unit_leader"


class DispatchOfferStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    expired = "expired"
    cancelled = "cancelled"


class ChatChannelType(str, enum.Enum):
    peer_to_peer = "peer_to_peer"
    group = "group"
    dispatch_to_unit = "dispatch_to_unit"
    command = "command"


class RunLogType(str, enum.Enum):
    incident = "incident"
    training = "training"
    meeting = "meeting"
    event = "event"
    other = "other"
