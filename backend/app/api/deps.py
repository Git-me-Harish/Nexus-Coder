from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import api_error
from app.core.security import decode_access_token, decode_sudo_token
from app.db.session import get_db
from app.models.user import TenantMember, User

bearer_scheme = HTTPBearer(auto_error=False)


class AuthContext:
    __slots__ = ("user_id", "tenant_id", "email")

    def __init__(self, user_id: str, tenant_id: str, email: str):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.email = email


async def get_auth_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthContext:
    if credentials is None:
        raise api_error(401, "UNAUTHORIZED", "Missing bearer token")
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise api_error(401, "UNAUTHORIZED", "Invalid or expired token")
    return AuthContext(user_id=payload["sub"], tenant_id=payload["tenant_id"], email=payload["email"])


async def get_current_user(
    ctx: Annotated[AuthContext, Depends(get_auth_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    user = await db.get(User, ctx.user_id)
    if user is None:
        raise api_error(401, "UNAUTHORIZED", "User no longer exists")
    return user


async def verify_tenant_membership(
    ctx: Annotated[AuthContext, Depends(get_auth_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthContext:
    stmt = select(TenantMember).where(
        TenantMember.user_id == ctx.user_id, TenantMember.tenant_id == ctx.tenant_id
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise api_error(403, "FORBIDDEN", "Not a member of this tenant")
    return ctx


async def require_sudo(
    ctx: Annotated[AuthContext, Depends(verify_tenant_membership)],
    x_sudo_token: Annotated[str | None, Header()] = None,
) -> AuthContext:
    """
    Step-up auth: a valid session is not enough, the caller must ALSO have
    re-entered their password recently (POST /auth/sudo).

    Enforced here rather than by hiding things in the UI, because a hidden
    screen protects nothing -- anyone holding the access token could call the
    route directly. The distinct SUDO_REQUIRED code is what tells the frontend
    to show the unlock prompt instead of logging the user out.
    """
    if not x_sudo_token:
        raise api_error(403, "SUDO_REQUIRED", "Confirm your password to access this.")

    payload = decode_sudo_token(x_sudo_token)
    if payload is None:
        raise api_error(403, "SUDO_REQUIRED", "Your confirmation has expired. Please confirm your password again.")

    # An elevation is only good for the account and tenant it was issued to --
    # otherwise one user's sudo token would elevate anyone else's session.
    if payload["sub"] != ctx.user_id or payload.get("tenant_id") != ctx.tenant_id:
        raise api_error(403, "SUDO_REQUIRED", "This confirmation isn't valid for the current account.")

    return ctx


CurrentAuth = Annotated[AuthContext, Depends(verify_tenant_membership)]
RequireSudo = Annotated[AuthContext, Depends(require_sudo)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_tenant_scoped_db(
    ctx: Annotated[AuthContext, Depends(verify_tenant_membership)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncSession:
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        await db.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": ctx.tenant_id}
        )
    return db


TenantDb = Annotated[AsyncSession, Depends(get_tenant_scoped_db)]