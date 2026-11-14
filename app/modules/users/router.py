"""Users + auth + sessions router."""

from __future__ import annotations

import hmac
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    client_ip, get_current_claims, get_db, rate_limit, require_role,
)
from app.core.exceptions import AppError
from app.core.pagination import clamp_limit, paginate
from shared.audit import log_async
from shared.enums import LoginOutcome, UserRole, UserStatus
from shared.models.identity import LoginAttempt, User, UserSession
from shared.rate_limit import allow
from shared.security import (
    create_access_token, create_refresh_token, decode_token,
    hash_password, hash_refresh_token, verify_password,
)
from shared.sessions import (
    bump_token_version, create_session, revoke_all_for_user, revoke_family,
    revoke_session,
)

# Roles a person may give themselves at sign-up. Coordinator and admin are
# granted only by an existing admin (dashboard, Users page, Role).
SELF_SERVICE_ROLES = frozenset({UserRole.citizen, UserRole.provider})

MAX_FAILED_LOGINS = 5
LOCKOUT = timedelta(minutes=15)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
Claims = Annotated[dict, Depends(get_current_claims)]


# ---- Schemas -----------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=2, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    role: UserRole = UserRole.citizen
    language: str = Field(default="en", max_length=5)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UpdateMeRequest(BaseModel):
    name: str | None = None
    phone: str | None = None
    language: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


def _user_public(u: User) -> dict:
    return {
        "id": str(u.id), "email": u.email, "name": u.name, "phone": u.phone,
        "role": u.role.value if hasattr(u.role, "value") else u.role,
        "status": u.status.value if hasattr(u.status, "value") else u.status,
        "language": u.language, "created_at": u.created_at.isoformat(),
    }


# ---- Auth --------------------------------------------------------------------
@router.post("/auth/register", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit("register", limit=10))])
async def register(data: RegisterRequest, db: DbSession):
    if data.role not in SELF_SERVICE_ROLES:
        raise AppError(403, "forbidden",
                       "That role cannot be self-registered. Ask an administrator.")

    # Deleted accounts are included on purpose: `users.email` is unique across
    # ALL rows, so an address that was ever used cannot be inserted again.
    existing = (await db.execute(
        select(User.id).where(User.email == data.email.lower())
    )).first()
    if existing:
        raise AppError(409, "email_exists", "That email is already registered.")

    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        name=data.name,
        phone=data.phone,
        role=data.role,
        status=UserStatus.active,   # MVP: auto-activate; email verification is FFP
        email_verified=True,
        language=data.language,
    )
    db.add(user)
    await db.flush()
    await log_async(db, actor_id=user.id, action="user.registered",
                    resource_type="user", resource_id=user.id,
                    new_values={"email": user.email, "role": data.role.value})
    return {"user": _user_public(user)}


@router.post("/auth/login", dependencies=[Depends(rate_limit("login", limit=5))])
async def login(data: LoginRequest, request: Request, db: DbSession):
    email = data.email.lower()
    ip = client_ip(request)

    # A second limit keyed on the account, so that spreading guesses over many
    # addresses does not get around the per-address limit above.
    if not allow("login_email", email, limit=10, per_seconds=300):
        raise AppError(429, "rate_limited",
                       "Too many attempts for this account. Try again later.")

    user = (await db.execute(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )).scalar_one_or_none()

    # NOTE: `get_db` rolls the transaction back when an error is raised.
    # Evidence of a failed attempt (the attempt row, the counter, the lock)
    # must survive, so each failure path commits BEFORE raising.

    if user is None:
        db.add(LoginAttempt(email=email, outcome=LoginOutcome.unknown_user, ip_address=ip,
                            occurred_at=datetime.now(UTC)))
        await db.commit()
        raise AppError(401, "invalid_credentials", "The email or password is incorrect.")

    if user.locked_until and user.locked_until > datetime.now(UTC):
        db.add(LoginAttempt(email=email, user_id=user.id, outcome=LoginOutcome.locked,
                            ip_address=ip, occurred_at=datetime.now(UTC)))
        await db.commit()
        raise AppError(403, "account_locked", "This account is temporarily locked.")

    if not verify_password(data.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_LOGINS:
            user.locked_until = datetime.now(UTC) + LOCKOUT
            user.failed_login_attempts = 0
        db.add(LoginAttempt(email=email, user_id=user.id,
                            outcome=LoginOutcome.bad_password, ip_address=ip,
                            occurred_at=datetime.now(UTC)))
        await db.commit()
        raise AppError(401, "invalid_credentials", "The email or password is incorrect.")

    if user.status != UserStatus.active:
        db.add(LoginAttempt(email=email, user_id=user.id, outcome=LoginOutcome.disabled,
                            ip_address=ip, occurred_at=datetime.now(UTC)))
        await db.commit()
        raise AppError(403, "forbidden", "Account is not active.")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(UTC)
    db.add(LoginAttempt(email=email, user_id=user.id,
                        outcome=LoginOutcome.success, ip_address=ip,
                        occurred_at=datetime.now(UTC)))

    # Mint a placeholder refresh token, create the session (which assigns the
    # real session id), then mint the real pair bound to that session.
    role = user.role.value if hasattr(user.role, "value") else user.role
    refresh, refresh_expires = create_refresh_token(
        str(user.id), role, "pending", str(uuid.uuid4()))
    session = await create_session(
        db, user=user, refresh_token=refresh, expires_at=refresh_expires,
        ip=ip, user_agent=request.headers.get("user-agent"),
    )
    access, expires_in = create_access_token(
        str(user.id), role, session.session_id, user.token_version)
    refresh, refresh_expires = create_refresh_token(
        str(user.id), role, session.session_id, str(session.refresh_token_family))
    session.refresh_token_hash = hash_refresh_token(refresh)
    session.expires_at = refresh_expires
    await db.flush()

    await log_async(db, actor_id=user.id, action="auth.login",
                    resource_type="user", resource_id=user.id, ip_address=ip)

    return {
        "user": _user_public(user),
        "tokens": {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "expires_in": expires_in,
            "refresh_strategy": "on_demand",
            "jitter_applied": True,
        },
    }


async def _on_refresh_reuse(db: AsyncSession, session: UserSession) -> None:
    """
    A refresh token that was already exchanged has been presented again.

    Only one party should ever hold the current token, so a stale one means
    it was copied. Kill the family, invalidate every token the user holds,
    record it, and commit, because the caller is about to raise.
    """
    await revoke_family(db, session.refresh_token_family)
    user = await db.get(User, session.user_id)
    if user is not None:
        await bump_token_version(db, user)
    await log_async(db, actor_id=None, action="auth.refresh_reuse_detected",
                    resource_type="user", resource_id=session.user_id,
                    new_values={"family": str(session.refresh_token_family)})
    await db.commit()


@router.post("/auth/refresh", dependencies=[Depends(rate_limit("refresh", limit=10))])
async def refresh(data: RefreshRequest, db: DbSession):
    try:
        claims = decode_token(data.refresh_token, expected_typ="refresh")
        sid = str(claims["sid"])
        user_id = uuid.UUID(str(claims["sub"]))
    except Exception as exc:
        raise AppError(401, "invalid_token", "Refresh token is invalid.") from exc

    # Lock the row so two simultaneous refreshes cannot both succeed.
    session = (await db.execute(
        select(UserSession).where(UserSession.session_id == sid).with_for_update()
    )).scalar_one_or_none()
    if session is None or session.user_id != user_id:
        raise AppError(401, "session_not_found", "Session not found.")

    if session.revoked_at is not None:
        raise AppError(401, "session_revoked", "Session has been revoked.")

    if session.expires_at <= datetime.now(UTC):
        raise AppError(401, "session_expired", "Session has expired.")

    # The session is alive but this is not its current token: reuse.
    presented = hash_refresh_token(data.refresh_token)
    if not hmac.compare_digest(session.refresh_token_hash, presented):
        await _on_refresh_reuse(db, session)
        raise AppError(401, "invalid_token", "Refresh token reuse detected.")

    user = await db.get(User, user_id)
    if user is None or user.status != UserStatus.active:
        raise AppError(401, "invalid_token", "Account is not active.")

    # Password change and forced logout bump the version: sessions issued
    # before that moment may not mint new tokens.
    if session.token_version_at_issue != user.token_version:
        raise AppError(401, "token_version_mismatch",
                       "This session is no longer valid. Sign in again.")

    role = user.role.value if hasattr(user.role, "value") else user.role
    sub, fam = str(user_id), str(session.refresh_token_family)
    new_refresh, new_expires = create_refresh_token(sub, role, sid, fam)
    session.refresh_token_hash = hash_refresh_token(new_refresh)
    session.expires_at = new_expires
    session.login_count += 1
    await db.flush()

    access, expires_in = create_access_token(sub, role, sid, user.token_version)
    return {
        "access_token": access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": expires_in,
    }


@router.post("/auth/logout")
async def logout(data: LogoutRequest, db: DbSession, auth: Claims):
    try:
        claims = decode_token(data.refresh_token, expected_typ="refresh")
    except Exception:
        return {"status": "signed_out"}
    # Only ever revoke a session that belongs to the caller.
    me_id = uuid.UUID(auth["sub"])
    await revoke_session(db, str(claims.get("sid", "")), by=me_id, user_id=me_id)
    return {"status": "signed_out"}


# ---- Profile -----------------------------------------------------------------
@router.get("/users/me")
async def me(claims: Claims, db: DbSession):
    user = await db.get(User, uuid.UUID(claims["sub"]))
    if user is None:
        raise AppError(404, "not_found", "User not found.")
    return _user_public(user)


@router.patch("/users/me")
async def update_me(data: UpdateMeRequest, claims: Claims, db: DbSession):
    user = await db.get(User, uuid.UUID(claims["sub"]))
    if user is None:
        raise AppError(404, "not_found", "User not found.")
    if data.name is not None:
        user.name = data.name
    if data.phone is not None:
        user.phone = data.phone
    if data.language is not None:
        user.language = data.language
    await db.flush()
    return _user_public(user)


@router.post("/users/me/change-password")
async def change_password(data: ChangePasswordRequest, claims: Claims, db: DbSession):
    user = await db.get(User, uuid.UUID(claims["sub"]))
    if user is None or not verify_password(data.current_password, user.password_hash):
        raise AppError(401, "invalid_credentials", "Current password is incorrect.")
    user.password_hash = hash_password(data.new_password)
    # Invalidate every access token AND end every session, so a copied
    # refresh token cannot be used to get back in.
    await bump_token_version(db, user)
    await revoke_all_for_user(db, user.id, by=user.id)
    await log_async(db, actor_id=user.id, action="user.password_changed",
                    resource_type="user", resource_id=user.id)
    return {"status": "password_changed"}


# ---- Sessions -----------------------------------------------------------------
@router.get("/users/me/sessions")
async def list_sessions(claims: Claims, db: DbSession):
    rows = list((await db.execute(
        select(UserSession).where(
            UserSession.user_id == uuid.UUID(claims["sub"]),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > datetime.now(UTC),
        ).order_by(UserSession.created_at.desc())
    )).scalars().all())
    return {"data": [
        {
            "session_id": s.session_id,
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "created_at": s.created_at.isoformat(),
            "last_activity_at": s.last_activity_at.isoformat() if s.last_activity_at else None,
            "expires_at": s.expires_at.isoformat(),
        } for s in rows
    ]}


@router.delete("/users/me/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_my_session(session_id: str, claims: Claims, db: DbSession):
    me_id = uuid.UUID(claims["sub"])
    if not await revoke_session(db, session_id, by=me_id, user_id=me_id):
        raise AppError(404, "not_found", "No such active session.")


# ---- Admin --------------------------------------------------------------------
@router.get("/users")
async def list_users(
    db: DbSession,
    _: Annotated[dict, Depends(require_role("admin"))],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    role: UserRole | None = None,
    status_filter: UserStatus | None = Query(None, alias="status"),
):
    conditions = [User.deleted_at.is_(None)]
    if role:
        conditions.append(User.role == role)
    if status_filter:
        conditions.append(User.status == status_filter)

    rows = list((await db.execute(
        select(User).where(*conditions)
        .order_by(User.created_at.desc())
        .offset((page - 1) * clamp_limit(limit))
        .limit(clamp_limit(limit))
    )).scalars().all())

    from sqlalchemy import func

    total = (await db.execute(
        select(func.count()).select_from(User).where(*conditions)
    )).scalar_one()

    return paginate([_user_public(u) for u in rows], total, page, clamp_limit(limit))

