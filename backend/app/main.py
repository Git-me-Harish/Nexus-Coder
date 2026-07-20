from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.memory import MemorySaver

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.middleware.rate_limit import RateLimitMiddleware

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.agents.graph import init_graph

    if settings.use_postgres_checkpointer:
        # Deferred import: langgraph-checkpoint-postgres + psycopg are
        # only required when this path is actually used, so a dev running
        # the default MemorySaver setup doesn't need them installed.
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(settings.checkpointer_conn_string) as checkpointer:
            await checkpointer.setup()  # idempotent — creates checkpoint tables if absent
            init_graph(checkpointer)
            yield
    else:
        init_graph(MemorySaver())
        yield

    from app.db.session import engine
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Nexus API",
        version="1.0.0",
        docs_url="/docs" if settings.env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()