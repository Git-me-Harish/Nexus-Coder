from fastapi import APIRouter

from app.api.v1.routes import (
    agent_stream, auth, credentials, files, github, knowledge, learning, models,
    preview, projects, providers, sessions, spec, tests, usage,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(sessions.router)
api_router.include_router(agent_stream.router)
api_router.include_router(files.router)
api_router.include_router(spec.router)
api_router.include_router(learning.router)
api_router.include_router(knowledge.router)
api_router.include_router(usage.router)
api_router.include_router(models.router)
api_router.include_router(providers.router)
api_router.include_router(credentials.router)
api_router.include_router(tests.router)
api_router.include_router(github.router)
api_router.include_router(preview.router)