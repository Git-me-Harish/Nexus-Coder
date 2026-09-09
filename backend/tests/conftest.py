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


@pytest.fixture(autouse=True)
def no_platform_provider_keys(monkeypatch):
    """
    Blank the platform fallback API keys for every test.

    credential_service.resolve_api_key falls back to settings.*_api_key when
    a tenant has no key of its own, and those are loaded from the developer's
    real backend/.env. Without this fixture the suite's behaviour depended on
    whose machine it ran on: the "no key configured" tests failed on any
    developer with keys in .env, and -- much worse -- the agent-stream test
    made a real, billed call to Anthropic and asserted against whatever a live
    model happened to say.

    A test that reaches the public internet is not a unit test. Any test that
    genuinely wants a platform key should monkeypatch it back on explicitly.
    """
    import app.services.credential_service as credential_service

    for attr in ("anthropic_api_key", "openai_api_key", "groq_api_key", "gemini_api_key"):
        monkeypatch.setattr(credential_service.settings, attr, None, raising=False)


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
async def db_session(app):
    """A session against the same in-memory DB the app fixture created, for
    tests that exercise services directly rather than through HTTP."""
    import app.db.session as dbsession

    async with dbsession.AsyncSessionLocal() as session:
        yield session


TEST_USER_PASSWORD = "password123!"


@pytest_asyncio.fixture
async def auth_headers(client):
    """Registers a fresh user and returns ready-to-use auth headers."""
    r = await client.post("/api/auth/register", json={
        "email": "test@example.com", "password": TEST_USER_PASSWORD, "name": "Test User",
    })
    assert r.status_code == 201, r.text
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def sudo_headers(client, auth_headers):
    """auth_headers plus a step-up elevation, for routes behind RequireSudo
    (provider credentials). Mirrors what the UI does after the user
    re-confirms their password."""
    r = await client.post("/api/auth/sudo", json={"password": TEST_USER_PASSWORD}, headers=auth_headers)
    assert r.status_code == 200, r.text
    return {**auth_headers, "X-Sudo-Token": r.json()["token"]}