"""
Database engines — one async (FastAPI), one sync (Flask dashboard).

Both point at the same database. Models live in `shared.models` and work
with either engine.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from shared.config import get_settings

_s = get_settings()

# ---- Async (FastAPI) ---------------------------------------------------------
async_engine = create_async_engine(
    _s.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
)

async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---- Sync (Flask dashboard) --------------------------------------------------
sync_engine = create_engine(
    _s.database_url_sync,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=1800,
    future=True,
)

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=sync_engine, autoflush=False, expire_on_commit=False, future=True
)


def get_sync_session() -> Generator[Session, None, None]:
    """Generator for the Flask request-scoped session."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
