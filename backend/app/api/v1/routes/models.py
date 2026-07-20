from fastapi import APIRouter

from app.agents.constants import MODELS
from app.api.deps import CurrentAuth, TenantDb
from app.services import credential_service

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
async def list_models(auth: CurrentAuth, db: TenantDb):
    provider_availability = {
        provider: await credential_service.tenant_has_usable_key(db, auth.tenant_id, provider)
        for provider in credential_service.SUPPORTED_PROVIDERS
    }
    models = [
        {**m, "available": provider_availability.get(m["provider"], False)}
        for m in MODELS
    ]
    return {"models": models}