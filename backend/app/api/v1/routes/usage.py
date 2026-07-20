from fastapi import APIRouter, Query

from app.api.deps import CurrentAuth, TenantDb
from app.services import usage_service

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("")
async def get_usage(auth: CurrentAuth, db: TenantDb, session_id: str | None = Query(default=None, alias="sessionId")):
    return await usage_service.get_usage(db, auth.tenant_id, auth.user_id, session_id)