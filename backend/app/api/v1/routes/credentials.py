"""
BYOK credential management -- Configure Models. A tenant's own provider
API keys, encrypted at rest (see app/core/crypto.py). The raw key is
never returned by any endpoint after save; only a masked preview.

EVERY route here requires step-up auth (RequireSudo), not just a signed-in
session: the caller must have re-entered their password within the last few
minutes. Being signed in is table stakes -- an unattended laptop or a lifted
access token clears that bar -- and this surface is worth more than that.
Reading it reveals which providers a tenant pays for, and writing to it lets
someone swap in a key whose bills land on somebody else.

Note what step-up does NOT do: the raw key was already unreadable through the
API before this, and still is. What it protects is the management surface
around it.
"""
from fastapi import APIRouter

from app.api.deps import RequireSudo, TenantDb
from app.schemas.credential import CredentialOut, CredentialSave
from app.services import credential_service

router = APIRouter(prefix="/providers/credentials", tags=["credentials"])


@router.get("")
async def list_credentials(auth: RequireSudo, db: TenantDb):
    return {"credentials": await credential_service.list_credentials(db, auth.tenant_id)}


@router.put("/{provider}")
async def save_credential(provider: str, payload: CredentialSave, auth: RequireSudo, db: TenantDb):
    result = await credential_service.save_credential(db, auth.tenant_id, auth.user_id, provider, payload.api_key)
    return {"credential": result}


@router.post("/{provider}/validate")
async def revalidate_credential(provider: str, auth: RequireSudo, db: TenantDb):
    result = await credential_service.revalidate_credential(db, auth.tenant_id, provider)
    return {"credential": result}


@router.delete("/{provider}")
async def delete_credential(provider: str, auth: RequireSudo, db: TenantDb):
    await credential_service.delete_credential(db, auth.tenant_id, provider)
    return {"ok": True}