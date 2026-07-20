"""
BYOK credential management -- Configure Models. A tenant's own provider
API keys, encrypted at rest (see app/core/crypto.py). The raw key is
never returned by any endpoint after save; only a masked preview.
"""
from fastapi import APIRouter

from app.api.deps import CurrentAuth, TenantDb
from app.schemas.credential import CredentialOut, CredentialSave
from app.services import credential_service

router = APIRouter(prefix="/providers/credentials", tags=["credentials"])


@router.get("")
async def list_credentials(auth: CurrentAuth, db: TenantDb):
    return {"credentials": await credential_service.list_credentials(db, auth.tenant_id)}


@router.put("/{provider}")
async def save_credential(provider: str, payload: CredentialSave, auth: CurrentAuth, db: TenantDb):
    result = await credential_service.save_credential(db, auth.tenant_id, auth.user_id, provider, payload.api_key)
    return {"credential": result}


@router.post("/{provider}/validate")
async def revalidate_credential(provider: str, auth: CurrentAuth, db: TenantDb):
    result = await credential_service.revalidate_credential(db, auth.tenant_id, provider)
    return {"credential": result}


@router.delete("/{provider}")
async def delete_credential(provider: str, auth: CurrentAuth, db: TenantDb):
    await credential_service.delete_credential(db, auth.tenant_id, provider)
    return {"ok": True}