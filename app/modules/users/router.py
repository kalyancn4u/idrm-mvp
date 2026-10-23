"""Users + auth + sessions router."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    client_ip, get_current_claims, get_db, get_optional_claims, require_role,
)
from app.core.exceptions import AppError
from app.core.pagination import clamp_limit, paginate
from shared.audit import log_async
from shared.config import get_settings
from shared.db import async_session
from shared.enums import LoginOutcome, UserRole, UserStatus
from shared.models.identity import LoginAttempt, User, UserSession
from shared.rate_limit import rate_limit
from shared.security import (
    create_access_token, create_refresh_token, decode_token,
    hash_password, hash_refresh_token, verify_password,
)
from shared.sessions import create_session, revoke_family, revoke_session

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
    existing = (await db.execute(
        select(User).where(User.email == data.email.lower(), User.deleted_at.is_(None))
    )).scalar_one_or_none()
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
    user = (await db.execute(
        select(User).where(User.email == data.email.lower(), User.deleted_at.is_(None))
    )).scalar_one_or_none()

    ip = client_ip(request)

    if user is None:
        db.add(LoginAttempt(email=data.email, outcome=LoginOutcome.unknown_user, ip_address=ip,
                            occurred_at=datetime.now(UTC)))
        await db.flush()
        raise AppError(401, "invalid_credentials", "The email or password is incorrect.")

    if user.locked_until and user.locked_until > datetime.now(UTC):
        raise AppError(403, "account_locked", "This account is temporarily locked.")

    if not verify_password(data.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.now(UTC) + timedelta(minutes=15)
        db.add(LoginAttempt(email=data.email, user_id=user.id,
                            outcome=LoginOutcome.bad_password, ip_address=ip,
                            occurred_at=datetime.now(UTC)))
        await db.flush()
        raise AppError(401, "invalid_credentials", "The email or password is incorrect.")

    if user.status != UserStatus.active:
        raise AppError(403, "forbidden", "Account is not active.")

    user.failed_login_attempts = 0
    user.last_login_at = datetime.now(UTC)
    db.add(LoginAttempt(email=data.email, user_id=user.id,
                        outcome=LoginOutcome.success, ip_address=ip,
                        occurred_at=datetime.now(UTC)))

    # Mint tokens
    role = user.role.value if hasattr(user.role, "value") else user.role
    access, expires_in = create_access_token(str(user.id), role, "pending", user.token_version)
    refresh, refresh_expires = create_refresh_token(str(user.id), role, "pending", str(uuid.uuid4()))

    # Create session (which assigns a real session_id) then re-mint
    session = await create_session(
        db, user=user, refresh_token=refresh, expires_at=refresh_expires,
        ip=ip, user_agent=request.headers.get("user-agent"),
    )
    access, expires_in = create_access_token(str(user.id), role, session.session_id, user.token_version)
    refresh, refresh_expires = create_refresh_token(str(user.id), role, session.session_id, str(session.refresh_token_family))
    session.refresh_token_hash = hash_refresh_token(refresh)
    await db.flush()

    await log_async(db, actor_id=user.id, action="auth.login",
                    resource_type="user", resource_id=user.id)

    settings = get_settings()
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


@router.post("/auth/refresh", dependencies=[Depends(rate_limit("refresh", limit=10))])
async def refresh(data: RefreshRequest, db: DbSession):
    try:
        claims = decode_token(data.refresh_token, expected_typ="refresh")
    except Exception as exc:
        raise AppError(401, "invalid_token", "Refresh token is invalid.") from exc

    sid = claims.get("sid")
    fam = claims.get("fam")
    sub = claims.get("sub")

    session = (await db.execute(
        select(UserSession).where(UserSession.session_id == sid)
    )).scalar_one_or_none()
    if session is None:
        raise AppError(401, "session_not_found", "Session not found.")

    # Reuse detection
    if session.revoked_at is not None:
        await revoke_family(db, uuid.UUID(fam))
        user = await db.get(User, uuid.UUID(sub))
        if user:
            user.token_version += 1
        await log_async(db, actor_id=None, action="auth.refresh_reuse_detected",
                        resource_type="user", resource_id=uuid.UUID(sub),
                        new_values={"family": fam}, ip_address=None)
        await db.flush()
        raise AppError(401, "invalid_token", "Refresh token reuse detected.")

    if session.expires_at <= datetime.now(UTC):
        raise AppError(401, "session_expired", "Session has expired.")

    # Verify hash matches
    if session.refresh_token_hash != hash_refresh_token(data.refresh_token):
        raise AppError(401, "invalid_token", "Refresh token does not match.")

    user = await db.get(User, uuid.UUID(sub))
    if user is None or user.status != UserStatus.active:
        raise AppError(401, "invalid_token", "Account is not active.")

    role = user.role.value if hasattr(user.role, "value") else user.role
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
async def logout(data: LogoutRequest, db: DbSession, _: Claims):
    try:
        claims = decode_token(data.refresh_token, expected_typ="refresh")
    except Exception:
        return {"status": "signed_out"}
    await revoke_session(db, claims.get("sid", ""))
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
    user.token_version += 1  # invalidate all tokens
    await db.flush()
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
    await revoke_session(db, session_id, by=uuid.UUID(claims["sub"]))


# ---- Admin --------------------------------------------------------------------
@router.get("/users")
async def list_users(
    db: DbSession,
    _: Annotated[dict, Depends(require_role("admin"))],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    role: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
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

