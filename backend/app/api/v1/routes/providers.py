"""Provider health/config status — was getProviderStatuses() in providers/index.ts."""
from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/providers", tags=["providers"])
settings = get_settings()


@router.get("/status")
async def provider_status():
    return {"providers": [
        {"name": "anthropic", "configured": bool(settings.anthropic_api_key)},
        {"name": "openai", "configured": bool(settings.openai_api_key)},
    ]}
