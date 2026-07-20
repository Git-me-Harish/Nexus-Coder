"""
Async SQLAlchemy engine/session against Postgres.

Postgres over SQLite is the single highest-leverage change in this
migration: SQLite serializes all writes (one writer at a time process-wide),
which cannot survive concurrent multi-tenant agent sessions each streaming
tokens and writing messages/usage rows. Postgres + asyncpg gives real
connection pooling and MVCC concurrency.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — one session per request, always closed."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def db_context() -> AsyncGenerator[AsyncSession, None]:
    """For use outside request scope — background jobs, LangGraph nodes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
