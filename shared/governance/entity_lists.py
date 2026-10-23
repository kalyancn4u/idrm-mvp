"""
Unified entity-list evaluation.

Order of resolution:
    1. allowlist with `allow_override` → allow (bypass blocklist)
    2. blocklist with `hard_block` → reject
    3. blocklist with `soft_block` → allow but flag
    4. watchlist → allow but log
    5. no match → allow, no intervention
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.cache import cached
from shared.enums import ListEffect
from shared.models.governance import EntityList, EntityListMatch


@cached("entity_lists:{entity_type}:{value}", ttl=30)
async def _load_matches(db: AsyncSession, entity_type: str, value: str) -> list[dict]:
    now = datetime.now(UTC)
    stmt = select(EntityList).where(
        EntityList.entity_type == entity_type,
        EntityList.entity_value == value,
        EntityList.active.is_(True),
        EntityList.effective_from <= now,
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return [
        {
            "id": str(r.id),
            "list_type": r.list_type.value if hasattr(r.list_type, "value") else r.list_type,
            "effect": r.effect.value if hasattr(r.effect, "value") else r.effect,
            "scope": r.scope,
        }
        for r in rows
        if r.effective_to is None or r.effective_to > now
    ]


async def evaluate(
    db: AsyncSession,
    *,
    subject_user_id: uuid.UUID | None,
    entity_type: str,
    value: str,
    context: dict | None = None,
) -> dict:
    """
    Return:
        { "allowed": bool, "effect": str | None, "match_id": str | None }
    """
    entries = await _load_matches(db, entity_type, value)

    allow_override = next((e for e in entries if e["effect"] == ListEffect.allow_override.value), None)
    if allow_override:
        await _record(db, allow_override["id"], entity_type, value, subject_user_id,
                      ListEffect.allow_override.value, context)
        return {"allowed": True, "effect": ListEffect.allow_override.value, "match_id": allow_override["id"]}

    hard_block = next((e for e in entries if e["effect"] == ListEffect.hard_block.value), None)
    if hard_block:
        await _record(db, hard_block["id"], entity_type, value, subject_user_id,
                      ListEffect.hard_block.value, context)
        return {"allowed": False, "effect": ListEffect.hard_block.value, "match_id": hard_block["id"]}

    soft_block = next((e for e in entries if e["effect"] == ListEffect.soft_block.value), None)
    if soft_block:
        await _record(db, soft_block["id"], entity_type, value, subject_user_id,
                      ListEffect.soft_block.value, context)
        return {"allowed": True, "effect": ListEffect.soft_block.value, "match_id": soft_block["id"]}

    watch = next((e for e in entries if e["effect"] == ListEffect.observe.value), None)
    if watch:
        await _record(db, watch["id"], entity_type, value, subject_user_id,
                      ListEffect.observe.value, context)
        return {"allowed": True, "effect": ListEffect.observe.value, "match_id": watch["id"]}

    return {"allowed": True, "effect": None, "match_id": None}


async def _record(
    db: AsyncSession,
    list_entry_id: str,
    entity_type: str,
    entity_value: str,
    subject_user_id: uuid.UUID | None,
    effect: str,
    context: dict | None,
) -> None:
    db.add(
        EntityListMatch(
            list_entry_id=uuid.UUID(list_entry_id),
            entity_type=entity_type,
            entity_value=entity_value,
            subject_user_id=subject_user_id,
            effect=effect,
            context=context or {},
            occurred_at=datetime.now(UTC),
        )
    )
    await db.flush()
