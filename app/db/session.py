from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache
def get_engine(database_url: str | None = None) -> AsyncEngine:
    resolved_database_url = database_url or get_settings().database_url
    return create_async_engine(resolved_database_url, pool_pre_ping=True)


@lru_cache
def get_async_session_factory(
    database_url: str | None = None,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(database_url),
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_db() -> AsyncIterator[AsyncSession]:
    async_session_factory = get_async_session_factory()
    async with async_session_factory() as session:
        yield session


async def dispose_engine(database_url: str | None = None) -> None:
    await get_engine(database_url).dispose()
    get_async_session_factory.cache_clear()
    get_engine.cache_clear()
