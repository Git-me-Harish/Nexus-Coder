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

from app.agents.constants import DEFAULT_MODEL_ID
from app.core.config import get_settings
from app.core.exceptions import api_error
from app.core.security import (
    create_access_token,
    create_sudo_token,
    generate_password_reset_token,
    generate_refresh_token,
    hash_password,
    hash_password_reset_token,
    hash_refresh_token,
    new_token_family,
    verify_password,
)
from app.models.learning import UserKnowledgeProfile  # noqa: F401 — ensures metadata registration
from app.models.user import PasswordResetToken, RefreshToken, Tenant, TenantMember, User, UserPreferences
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    PreferencesUpdateRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    ResetPasswordRequest,
)

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
        db.add(UserPreferences(user_id=user.id, default_mode="development", default_model_id=DEFAULT_MODEL_ID, theme="dark"))
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


async def login_or_register_with_github(
    db: AsyncSession, *, github_user_id: str, login: str,
    email: str | None, name: str | None, avatar_url: str | None,
) -> tuple[User, Tenant]:
    """
    "Continue with GitHub" -- signs in an existing account or creates one.

    Matching runs in a deliberate order:
      1. github_user_id: GitHub's stable numeric id, so a renamed login still
         lands on the same Nexus account.
      2. verified email: links GitHub to an account that already registered
         with the same address, instead of silently creating a duplicate.
         github_service.fetch_github_email only ever returns a VERIFIED
         address, which is what makes this safe -- an unverified match would
         let anyone claim an account by adding its email to their GitHub.
      3. otherwise a new user + tenant, mirroring register(), just with no
         password (see User.has_password and change_password).
    """
    user = (await db.execute(
        select(User).where(User.github_user_id == github_user_id)
    )).scalar_one_or_none()

    if user is None and email:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()

    if user is None:
        if not email:
            raise api_error(
                400, "GITHUB_NO_VERIFIED_EMAIL",
                "Your GitHub account has no verified email address, so we can't create an account from it. "
                "Verify an email on GitHub, or sign up with an email and password instead.",
            )
        display_name = name or login
        tenant_name = f"{display_name}'s Workspace"
        tenant = Tenant(name=tenant_name, slug=await _unique_tenant_slug(db, tenant_name), plan="free", token_budget=500_000)
        db.add(tenant)
        await db.flush()

        user = User(
            email=email, name=display_name, password_hash=None,
            avatar_url=avatar_url, github_username=login, github_user_id=github_user_id,
        )
        db.add(user)
        await db.flush()

        db.add(TenantMember(tenant_id=tenant.id, user_id=user.id, role="owner"))
        db.add(UserPreferences(user_id=user.id, default_mode="development", default_model_id=DEFAULT_MODEL_ID, theme="dark"))
        await db.commit()
        return user, tenant

    # Existing account: (re)bind the GitHub identity and fill in only what is
    # still blank -- a name or avatar the user set here outranks GitHub's.
    user.github_user_id = github_user_id
    user.github_username = login
    if not user.name and name:
        user.name = name
    if not user.avatar_url and avatar_url:
        user.avatar_url = avatar_url

    membership = (await db.execute(select(TenantMember).where(TenantMember.user_id == user.id))).scalars().first()
    if membership is None:
        raise api_error(403, "NO_TENANT", "User has no tenant membership.")
    tenant = await db.get(Tenant, membership.tenant_id)
    await db.commit()
    return user, tenant


async def issue_tokens_for_user(db: AsyncSession, user_id: str, tenant_id: str) -> AuthResponse:
    """Used by the GitHub sign-in exchange: the identity was already proven by
    the OAuth callback, so this only mints the session."""
    user = await db.get(User, user_id)
    tenant = await db.get(Tenant, tenant_id)
    if user is None or tenant is None:
        raise api_error(401, "INVALID_EXCHANGE", "This sign-in link is no longer valid.")
    return await _issue_tokens(db, user=user, tenant=tenant)


async def _revoke_outstanding_reset_tokens(db: AsyncSession, user_id: str) -> None:
    """Any pending "reset your password" link stops working the moment the
    password changes by another route -- otherwise an old link sitting in an
    inbox could undo a deliberate change (or a compromise response)."""
    await db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
        .values(used_at=datetime.now(timezone.utc))
    )


async def request_password_reset(db: AsyncSession, email: str) -> tuple[str, str] | None:
    """
    Issues a reset token, returning (email, raw_token) for the caller to mail,
    or None when nothing should be sent.

    Returning None rather than raising is the whole point: the ROUTE always
    answers the same way whether or not the address exists, so this endpoint
    cannot be used to discover who has an account. Every "don't send" reason
    -- unknown address, one already sent moments ago -- looks identical from
    the outside.

    Accounts created through GitHub with no password are deliberately
    included: setting a first password by proving control of the verified
    email is legitimate, and is the same thing the Security tab offers.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)

    user = (await db.execute(select(User).where(User.email == email.lower()))).scalar_one_or_none()
    if user is None:
        return None

    # Per-account throttle. The global IP rate limit does not stop someone
    # pointing a flood of reset emails at one victim's inbox; this does, and
    # it costs one indexed query.
    recent = (await db.execute(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .order_by(PasswordResetToken.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if recent is not None and (now - _as_aware(recent.created_at)).total_seconds() < 60:
        return None

    # Only the newest link should work; supersede anything still outstanding.
    await _revoke_outstanding_reset_tokens(db, user.id)

    raw, token_hash = generate_password_reset_token()
    db.add(PasswordResetToken(
        user_id=user.id, token_hash=token_hash, created_at=now,
        expires_at=now + timedelta(minutes=settings.password_reset_ttl_minutes),
    ))
    await db.commit()
    return user.email, raw


async def reset_password(db: AsyncSession, payload: ResetPasswordRequest) -> AuthResponse:
    """
    Consumes a reset link and signs the user in on the new password.

    Every failure mode collapses into one generic error on purpose -- a
    distinct "expired" vs "already used" vs "no such token" would tell an
    attacker probing tokens which guesses were closer.
    """
    now = datetime.now(timezone.utc)
    invalid = api_error(
        400, "INVALID_RESET_TOKEN",
        "This password reset link is invalid, has expired, or has already been used. "
        "Request a new one to try again.",
    )

    row = (await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_password_reset_token(payload.token)
        )
    )).scalar_one_or_none()

    if row is None or row.used_at is not None or _as_aware(row.expires_at) < now:
        raise invalid

    user = await db.get(User, row.user_id)
    if user is None:
        raise invalid

    membership = (await db.execute(select(TenantMember).where(TenantMember.user_id == user.id))).scalars().first()
    if membership is None:
        raise api_error(403, "NO_TENANT")
    tenant = await db.get(Tenant, membership.tenant_id)

    user.password_hash = hash_password(payload.new_password)
    row.used_at = now
    await _revoke_outstanding_reset_tokens(db, user.id)
    # Whoever prompted this reset may already hold a session. Ending all of
    # them is the point of resetting a password, so every refresh token dies
    # here and the caller gets a brand-new pair below.
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    return await _issue_tokens(db, user=user, tenant=tenant)


async def change_password(db: AsyncSession, user_id: str, payload: ChangePasswordRequest) -> AuthResponse:
    """
    Sets or replaces the account password, then ends every other session.

    Revoking all outstanding refresh tokens is the point of changing a
    password after a suspected compromise -- leaving them alive would let
    whoever prompted the change keep refreshing indefinitely. The caller gets
    a brand-new pair back so the tab they did this in stays signed in.
    """
    user = await db.get(User, user_id)
    if user is None:
        raise api_error(404, "USER_NOT_FOUND")

    if user.password_hash is not None:
        if not payload.current_password or not verify_password(payload.current_password, user.password_hash):
            raise api_error(400, "INVALID_CURRENT_PASSWORD", "Your current password is incorrect.")
        if payload.current_password == payload.new_password:
            raise api_error(400, "PASSWORD_UNCHANGED", "Your new password must be different from your current one.")

    membership = (await db.execute(select(TenantMember).where(TenantMember.user_id == user.id))).scalars().first()
    if membership is None:
        raise api_error(403, "NO_TENANT")
    tenant = await db.get(Tenant, membership.tenant_id)

    user.password_hash = hash_password(payload.new_password)
    await _revoke_outstanding_reset_tokens(db, user.id)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    return await _issue_tokens(db, user=user, tenant=tenant)


async def elevate_to_sudo(db: AsyncSession, user_id: str, tenant_id: str, password: str) -> str:
    """
    Re-checks the account password and returns a short-lived elevation token.

    Brute-force resistance here rests on Argon2id's cost (~100ms per attempt
    with this configuration) plus the global per-IP rate limit, rather than a
    lockout counter -- stated plainly because "there is a lockout" would be
    the wrong thing to assume. Adding one means somewhere to keep the counter,
    which is a Redis dependency this route does not currently take.
    """
    user = await db.get(User, user_id)
    if user is None:
        raise api_error(404, "USER_NOT_FOUND")

    if user.password_hash is None:
        # Signed up through GitHub and never set a password: there is nothing
        # to re-check, so point them at the one place that fixes it rather
        # than either locking them out or waving them through.
        raise api_error(
            409, "PASSWORD_NOT_SET",
            "This account signs in with GitHub and has no password yet. "
            "Set one under Security first, then confirm it here.",
        )

    if not verify_password(password, user.password_hash):
        raise api_error(401, "INVALID_PASSWORD", "That password is incorrect.")

    return create_sudo_token(user_id=user.id, tenant_id=tenant_id)


async def set_avatar_url(db: AsyncSession, user_id: str, url: str | None) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise api_error(404, "USER_NOT_FOUND")
    user.avatar_url = url
    await db.commit()
    await db.refresh(user)
    return user


async def get_me(db: AsyncSession, user_id: str, tenant_id: str):
    user = await db.get(User, user_id)
    if user is None:
        raise api_error(404, "USER_NOT_FOUND")
    tenant = await db.get(Tenant, tenant_id)
    prefs = (await db.execute(select(UserPreferences).where(UserPreferences.user_id == user_id))).scalar_one_or_none()
    return user, tenant, prefs


async def update_profile(db: AsyncSession, user_id: str, payload: ProfileUpdateRequest) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise api_error(404, "USER_NOT_FOUND")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


async def update_preferences(db: AsyncSession, user_id: str, payload: PreferencesUpdateRequest) -> UserPreferences:
    prefs = (await db.execute(select(UserPreferences).where(UserPreferences.user_id == user_id))).scalar_one_or_none()
    if prefs is None:
        prefs = UserPreferences(user_id=user_id, default_mode="development", default_model_id=DEFAULT_MODEL_ID, theme="dark")
        db.add(prefs)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if value is not None:
            setattr(prefs, field, value)
    await db.commit()
    await db.refresh(prefs)
    return prefs


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