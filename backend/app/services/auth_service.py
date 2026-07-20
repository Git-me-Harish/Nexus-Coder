"""
Auth business logic — response shape matches the frontend's authStore
exactly: { token, refreshToken, user, tenant }. `token` is a real,
validated JWT (see app/core/security.py) rather than the original
homegrown HMAC scheme; `refreshToken` is new — the original frontend had
no refresh flow at all behind its 15-min token, which silently logged
users out. client.ts now uses it (see frontend/src/lib/nexus/client.ts).
"""
from datetime import datetime, timedelta, timezone
import re

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import api_error
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    new_token_family,
    verify_password,
)
from app.models.learning import UserKnowledgeProfile  # noqa: F401 — ensures metadata registration
from app.models.user import RefreshToken, Tenant, TenantMember, User, UserPreferences
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest

settings = get_settings()


def _as_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


async def register(db: AsyncSession, payload: RegisterRequest) -> AuthResponse:
    existing = (await db.execute(select(User).where(User.email == payload.email.lower()))).scalar_one_or_none()
    if existing is not None:
        raise api_error(409, "EMAIL_TAKEN", "An account with this email already exists.")

    display_name = payload.name or payload.email.split("@")[0]
    tenant_name = payload.tenant_name or f"{display_name}'s Workspace"
    slug = await _unique_tenant_slug(db, tenant_name)

    try:
        tenant = Tenant(name=tenant_name, slug=slug, plan="free", token_budget=500_000)
        db.add(tenant)
        await db.flush()

        user = User(email=payload.email.lower(), name=display_name, password_hash=hash_password(payload.password))
        db.add(user)
        await db.flush()

        db.add(TenantMember(tenant_id=tenant.id, user_id=user.id, role="owner"))
        db.add(UserPreferences(user_id=user.id, default_mode="development", default_model_id="claude-sonnet-4-6", theme="dark"))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise api_error(409, "EMAIL_TAKEN", "An account with this email already exists.")

    return await _issue_tokens(db, user=user, tenant=tenant)


async def _unique_tenant_slug(db: AsyncSession, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "workspace"
    slug = base
    suffix = 1
    while (await db.execute(select(Tenant).where(Tenant.slug == slug))).scalar_one_or_none() is not None:
        suffix += 1
        slug = f"{base}-{suffix}"
    return slug


async def login(db: AsyncSession, payload: LoginRequest) -> AuthResponse:
    user = (await db.execute(select(User).where(User.email == payload.email.lower()))).scalar_one_or_none()
    dummy_hash = "$argon2id$v=19$m=65536,t=3,p=4$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    password_hash = user.password_hash if user and user.password_hash else dummy_hash
    valid = verify_password(payload.password, password_hash)

    if not user or not valid:
        raise api_error(401, "INVALID_CREDENTIALS", "Invalid email or password.")

    membership = (await db.execute(select(TenantMember).where(TenantMember.user_id == user.id))).scalars().first()
    if membership is None:
        raise api_error(403, "NO_TENANT", "User has no tenant membership.")
    tenant = await db.get(Tenant, membership.tenant_id)

    return await _issue_tokens(db, user=user, tenant=tenant)


async def refresh(db: AsyncSession, raw_refresh_token: str) -> AuthResponse:
    token_hash = hash_refresh_token(raw_refresh_token)
    token_row = (await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))).scalar_one_or_none()

    if token_row is None:
        raise api_error(401, "INVALID_REFRESH_TOKEN")

    if token_row.revoked_at is not None:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == token_row.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await db.commit()
        raise api_error(401, "REFRESH_REUSE_DETECTED", "Refresh token reuse detected — session revoked.")

    if _as_aware(token_row.expires_at) < datetime.now(timezone.utc):
        raise api_error(401, "REFRESH_EXPIRED")

    user = await db.get(User, token_row.user_id)
    if user is None:
        raise api_error(401, "USER_NOT_FOUND")

    membership = (await db.execute(select(TenantMember).where(TenantMember.user_id == user.id))).scalars().first()
    if membership is None:
        raise api_error(403, "NO_TENANT")
    tenant = await db.get(Tenant, membership.tenant_id)

    token_row.revoked_at = datetime.now(timezone.utc)
    response = await _issue_tokens(db, user=user, tenant=tenant, family_id=token_row.family_id)
    await db.commit()
    return response


async def get_me(db: AsyncSession, user_id: str, tenant_id: str):
    user = await db.get(User, user_id)
    if user is None:
        raise api_error(404, "USER_NOT_FOUND")
    tenant = await db.get(Tenant, tenant_id)
    prefs = (await db.execute(select(UserPreferences).where(UserPreferences.user_id == user_id))).scalar_one_or_none()
    return user, tenant, prefs


async def _issue_tokens(db: AsyncSession, *, user: User, tenant: Tenant, family_id: str | None = None) -> AuthResponse:
    access_token = create_access_token(user_id=user.id, tenant_id=tenant.id, email=user.email)
    raw_refresh, refresh_hash = generate_refresh_token()

    db.add(RefreshToken(
        user_id=user.id, token_hash=refresh_hash, family_id=family_id or new_token_family(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_ttl_days),
        created_at=datetime.now(timezone.utc),
    ))
    await db.commit()

    return AuthResponse(
        token=access_token, refresh_token=raw_refresh,
        user=user, tenant=tenant,
    )