from fastapi import APIRouter

from app.api.v1.routes import (
    agent_stream, auth, credentials, files, knowledge, learning, models,
    projects, providers, sessions, spec, usage,
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