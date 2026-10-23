"""Health, info, reports."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from shared.config import get_settings
from shared.db import async_engine
from shared.db import async_session
from shared.models.identity import User
from shared.models.incident import Incident
from shared.models.organization import Organization

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/health")
async def health():
    ok, detail = True, "ok"
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        ok, detail = False, str(exc)
    return {"status": "ok" if ok else "degraded", "version": "0.1.0",
            "components": {"database": {"ok": ok, "detail": detail}}}


@router.get("/info")
async def info():
    s = get_settings()
    return {"app_name": s.app_name, "app_tagline": s.app_tagline,
            "environment": s.app_env, "supported_languages": ["en", "hi", "te"]}


@router.get("/reports/summary")
async def summary(
    db: DbSession,
    _: Annotated[dict, Depends(require_role("coordinator", "admin"))],
):
    users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    orgs = (await db.execute(select(func.count()).select_from(Organization))).scalar_one()
    incidents = (await db.execute(select(func.count()).select_from(Incident))).scalar_one()
    return {"users": users, "organizations": orgs, "incidents": incidents}

