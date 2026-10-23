"""Messages, chat, notifications router."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_claims, get_db, require_role
from app.core.pagination import clamp_limit, paginate
from shared.db import async_session
from shared.models.comms import ChatChannel, ChatMessage, Message, Notification

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
Claims = Annotated[dict, Depends(get_current_claims)]


class MessageCreate(BaseModel):
    organization_id: uuid.UUID
    title: str = Field(min_length=3, max_length=255)
    body: str = Field(min_length=10)
    target_roles: list[str] = []
    target_users: list[uuid.UUID] = []


class ChatMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


# ---- Messages -----------------------------------------------------------------
@router.post("/messages", status_code=status.HTTP_201_CREATED)
async def send_message(
    body: MessageCreate, db: DbSession,
    claims: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    m = Message(
        organization_id=body.organization_id, sender_id=uuid.UUID(claims["sub"]),
        title=body.title, body=body.body,
        target_roles=body.target_roles, target_users=body.target_users,
        sent_at=datetime.now(UTC),
    )
    db.add(m)
    await db.flush()
    return {"id": str(m.id)}


# ---- Chat ---------------------------------------------------------------------
@router.post("/chat/channels", status_code=status.HTTP_201_CREATED)
async def create_channel(
    payload: dict, db: DbSession, claims: Claims,
):
    c = ChatChannel(
        channel_type=payload.get("channel_type", "group"),
        organization_id=payload.get("organization_id"),
        incident_id=payload.get("incident_id"),
        unit_id=payload.get("unit_id"),
        name=payload.get("name"),
        created_by=uuid.UUID(claims["sub"]),
        created_at=datetime.now(UTC),
    )
    db.add(c)
    await db.flush()
    return {"id": str(c.id)}


@router.get("/chat/channels/{channel_id}/messages")
async def list_chat_messages(
    channel_id: uuid.UUID, db: DbSession, claims: Claims,
    page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=200),
):
    from sqlalchemy import func

    conditions = [ChatMessage.channel_id == channel_id]
    total = (await db.execute(
        select(func.count()).select_from(ChatMessage).where(*conditions)
    )).scalar_one()
    rows = list((await db.execute(
        select(ChatMessage).where(*conditions)
        .order_by(ChatMessage.sent_at.desc())
        .offset((page - 1) * clamp_limit(limit))
        .limit(clamp_limit(limit))
    )).scalars().all())
    return paginate(
        [{"id": str(r.id), "sender_id": str(r.sender_id),
          "body": r.body, "sent_at": r.sent_at.isoformat()}
         for r in rows],
        total, page, clamp_limit(limit),
    )


@router.post("/chat/channels/{channel_id}/messages", status_code=status.HTTP_201_CREATED)
async def post_chat_message(
    channel_id: uuid.UUID, body: ChatMessageCreate, db: DbSession, claims: Claims,
):
    m = ChatMessage(
        channel_id=channel_id, sender_id=uuid.UUID(claims["sub"]),
        body=body.body, sent_at=datetime.now(UTC),
    )
    db.add(m)
    await db.flush()
    return {"id": str(m.id)}


# ---- Notifications ------------------------------------------------------------
@router.get("/notifications")
async def list_notifications(
    db: DbSession, claims: Claims,
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
):
    from sqlalchemy import func

    conditions = [Notification.user_id == uuid.UUID(claims["sub"]),
                  Notification.deleted_at.is_(None)]
    if unread_only:
        conditions.append(Notification.is_read.is_(False))

    total = (await db.execute(
        select(func.count()).select_from(Notification).where(*conditions)
    )).scalar_one()
    rows = list((await db.execute(
        select(Notification).where(*conditions)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * clamp_limit(limit))
        .limit(clamp_limit(limit))
    )).scalars().all())
    return paginate(
        [{"id": str(r.id), "title": r.title, "message": r.message,
          "type": r.type.value if hasattr(r.type, "value") else r.type,
          "is_read": r.is_read, "link": r.link,
          "created_at": r.created_at.isoformat()}
         for r in rows],
        total, page, clamp_limit(limit),
    )


@router.post("/notifications/{notification_id}/read")
async def mark_read(notification_id: uuid.UUID, db: DbSession, claims: Claims):
    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id,
               Notification.user_id == uuid.UUID(claims["sub"]))
        .values(is_read=True)
    )
    return {"status": "read"}


@router.post("/notifications/read-all")
async def mark_all_read(db: DbSession, claims: Claims):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == uuid.UUID(claims["sub"]),
               Notification.is_read.is_(False))
        .values(is_read=True)
    )
    return {"status": "all_read"}

