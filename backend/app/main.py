import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.memory import MemorySaver

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.middleware.rate_limit import RateLimitMiddleware

settings = get_settings()
logger = logging.getLogger("nexus")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.agents.graph import init_graph
    from app.agents.sandbox import sandbox_health

    # Checked at startup, before serving: an operator who set SANDBOX_ENABLED
    # but never built the image would otherwise only discover it from quietly
    # degraded agent turns -- the agent keeps writing files but silently loses
    # the ability to verify any of them.
    status = await sandbox_health()
    if status["enabled"] and not status["usable"]:
        logger.warning(
            "Sandbox is enabled but NOT usable (%s) -- the agent can write files but "
            "cannot run commands, so it cannot verify the code it writes.", status["detail"],
        )
    elif status["usable"]:
        logger.info("Sandbox ready: %s", status["detail"])

    # Live preview runs a second, network-enabled container per session (see
    # app/agents/preview.py); this background tick is what stops one a user
    # has stopped looking at rather than leaving it running indefinitely.
    reaper_task: asyncio.Task | None = None
    if settings.preview_enabled:
        from app.agents.preview import reap_idle_previews

        async def _reaper_loop() -> None:
            while True:
                await asyncio.sleep(60)
                try:
                    await reap_idle_previews()
                except Exception:  # noqa: BLE001 -- one bad tick must not kill the reaper
                    logger.exception("preview idle-reaper tick failed")

        reaper_task = asyncio.create_task(_reaper_loop())
        logger.info("Preview idle reaper started (timeout=%dm)", settings.preview_idle_timeout_minutes)

    try:
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
    finally:
        if reaper_task is not None:
            reaper_task.cancel()
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

    # Uploaded profile avatars. Only raster image types ever get written here
    # and the filenames are generated server-side (see
    # app/services/avatar_service.py), so StaticFiles has nothing user-supplied
    # to resolve and serves each file under the Content-Type its own extension
    # implies.
    from app.services.avatar_service import avatar_dir

    app.mount("/uploads/avatars", StaticFiles(directory=avatar_dir()), name="avatars")

    @app.get("/health")
    async def health():
        # The sandbox's state is worth surfacing: with it unusable the agent
        # silently loses run_command, so it can still write files but can no
        # longer verify anything it wrote. That degradation is invisible from
        # the outside otherwise -- turns just quietly get less trustworthy.
        from app.agents.preview import preview_health
        from app.agents.sandbox import sandbox_health

        return {"status": "ok", "sandbox": await sandbox_health(), "preview": await preview_health()}

    return app


app = create_app()