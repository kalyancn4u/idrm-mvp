"""Entity list evaluation logic — with a mocked DB."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch


def test_evaluate_returns_allowed_when_no_match():
    """When there are no list entries, everything is allowed."""
    import asyncio

    from shared.governance import entity_lists

    async def _run():
        with patch.object(entity_lists, "_load_matches", AsyncMock(return_value=[])):
            db = AsyncMock()
            result = await entity_lists.evaluate(
                db, subject_user_id=None, entity_type="email", value="x@y.z"
            )
            assert result["allowed"] is True
            assert result["effect"] is None

    asyncio.run(_run())


def test_evaluate_hard_block():
    import asyncio

    from shared.governance import entity_lists

    entries = [{"id": "00000000-0000-4000-8000-000000000001",
                "list_type": "blocklist", "effect": "hard_block", "scope": {}}]

    async def _run():
        with patch.object(entity_lists, "_load_matches", AsyncMock(return_value=entries)), \
             patch.object(entity_lists, "_record", AsyncMock()):
            db = AsyncMock()
            result = await entity_lists.evaluate(
                db, subject_user_id=None, entity_type="email", value="bad@x.y"
            )
            assert result["allowed"] is False
            assert result["effect"] == "hard_block"

    asyncio.run(_run())


def test_allow_override_beats_hard_block():
    import asyncio

    from shared.governance import entity_lists

    entries = [
        {"id": "00000000-0000-4000-8000-000000000001",
         "list_type": "blocklist", "effect": "hard_block", "scope": {}},
        {"id": "00000000-0000-4000-8000-000000000002",
         "list_type": "allowlist", "effect": "allow_override", "scope": {}},
    ]

    async def _run():
        with patch.object(entity_lists, "_load_matches", AsyncMock(return_value=entries)), \
             patch.object(entity_lists, "_record", AsyncMock()):
            db = AsyncMock()
            result = await entity_lists.evaluate(
                db, subject_user_id=None, entity_type="email", value="x@y.z"
            )
            assert result["allowed"] is True
            assert result["effect"] == "allow_override"

    asyncio.run(_run())
