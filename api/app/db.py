"""PostgreSQL access (system of record). Only the API connects; voice/ never does."""
from collections.abc import AsyncIterator

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def async_url(url: str) -> str:
    """Accept postgresql:// or postgres:// (Neon, Cloud SQL) and force the asyncpg driver."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]
    return url


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        url = get_settings().database_url
        if not url:
            raise RuntimeError("DATABASE_URL is not set (see api/.env.example)")
        _engine = create_async_engine(async_url(url), pool_pre_ping=True)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def new_session() -> AsyncSession:
    """A session outside a request (the dispatch loop). Use as `async with new_session()`."""
    get_engine()
    assert _sessionmaker is not None
    return _sessionmaker()


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request; routes commit explicitly."""
    try:
        get_engine()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Database not configured") from exc
    assert _sessionmaker is not None
    async with _sessionmaker() as session:
        yield session
