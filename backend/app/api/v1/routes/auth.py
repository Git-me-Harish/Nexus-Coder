from fastapi import APIRouter

from app.api.deps import CurrentAuth, DbSession
from app.schemas.auth import AuthResponse, LoginRequest, MeResponse, RefreshRequest, RegisterRequest
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(payload: RegisterRequest, db: DbSession):
    return await auth_service.register(db, payload)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: DbSession):
    return await auth_service.login(db, payload)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(payload: RefreshRequest, db: DbSession):
    return await auth_service.refresh(db, payload.refresh_token)


@router.get("/me", response_model=MeResponse)
async def me(auth: CurrentAuth, db: DbSession):
    user, tenant, prefs = await auth_service.get_me(db, auth.user_id, auth.tenant_id)
    return MeResponse(user=user, tenant=tenant, preferences=prefs)


@router.post("/me")
async def logout():
    # Tokens are stateless JWTs; the client discards them. Refresh tokens
    # remain valid until natural expiry — for immediate server-side logout,
    # revoke the token family here via auth_service in a future pass.
    return {"ok": True}
