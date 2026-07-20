import os

os.environ.setdefault("JWT_SECRET", "test-secret-abcdefghijklmnopqrstuvwxyz0123456789")
# Fixed (not randomly generated) so test runs are reproducible -- this is a
# throwaway key for the test suite only, never used against real data.
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", "w870Yl4xuTV7kxgA5dlD6K4KTd4ioaCE0lvEuHgOy6M=")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")  # unused; overridden below

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def app(monkeypatch):
    """Fresh app + fresh in-memory DB + fresh compiled graph per test --
    no state leaks between tests."""
    import app.db.session as dbsession
    from app.db.base import Base
    import app.models  # noqa: F401 -- registers all tables on Base.metadata

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=None)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    dbsession.engine = engine
    dbsession.AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

    from app.agents.graph import init_graph
    init_graph(MemorySaver())

    import app.main as main_mod
    yield main_mod.app

    await engine.dispose()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_headers(client):
    """Registers a fresh user and returns ready-to-use auth headers."""
    r = await client.post("/api/auth/register", json={
        "email": "test@example.com", "password": "password123!", "name": "Test User",
    })
    assert r.status_code == 201, r.text
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}