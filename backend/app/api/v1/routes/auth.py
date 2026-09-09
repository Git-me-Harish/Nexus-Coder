import logging
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, File, UploadFile

from app.api.deps import CurrentAuth, DbSession
from app.core.config import get_settings
from app.core.exceptions import api_error
from app.core.security import decode_auth_exchange_token
from app.schemas.auth import (
    AuthResponse, AvatarResponse, ChangePasswordRequest, ForgotPasswordRequest,
    GithubExchangeRequest, LoginRequest, MeResponse, PreferencesOut,
    PreferencesUpdateRequest, ProfileUpdateRequest, RefreshRequest,
    RegisterRequest, ResetPasswordRequest, SudoRequest, SudoResponse, UserOut,
)
from app.services import auth_service, avatar_service, email_service, github_service

logger = logging.getLogger("nexus.api.auth")

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


@router.post("/logout")
async def logout():
    # Tokens are stateless JWTs; the client discards them. Refresh tokens
    # remain valid until natural expiry — for immediate server-side logout,
    # revoke the token family here via auth_service in a future pass.
    return {"ok": True}


@router.patch("/me", response_model=UserOut)
async def update_me(payload: ProfileUpdateRequest, auth: CurrentAuth, db: DbSession):
    return await auth_service.update_profile(db, auth.user_id, payload)


@router.patch("/preferences", response_model=PreferencesOut)
async def update_preferences(payload: PreferencesUpdateRequest, auth: CurrentAuth, db: DbSession):
    return await auth_service.update_preferences(db, auth.user_id, payload)


@router.post("/change-password", response_model=AuthResponse)
async def change_password(payload: ChangePasswordRequest, auth: CurrentAuth, db: DbSession):
    """Returns a fresh token pair: changing a password revokes every
    outstanding refresh token, this session's included."""
    return await auth_service.change_password(db, auth.user_id, payload)


@router.post("/sudo", response_model=SudoResponse)
async def elevate(payload: SudoRequest, auth: CurrentAuth, db: DbSession):
    """
    Step-up auth: re-confirm the password to unlock the API-key management
    surface for a few minutes. The returned token goes back as X-Sudo-Token
    and is meant to be held in memory only -- see app/api/deps.require_sudo.
    """
    token = await auth_service.elevate_to_sudo(db, auth.user_id, auth.tenant_id, payload.password)
    return SudoResponse(token=token, expires_in_minutes=get_settings().sudo_ttl_minutes)


# Forgot / reset password (public)
@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, db: DbSession, background: BackgroundTasks):
    """
    ALWAYS answers the same way, whether or not that address has an account.

    Anything else turns this into an account-enumeration oracle: a different
    status, message, or even a noticeably different response time would let
    anyone check which emails are registered here. That is also why the email
    goes out as a background task -- the response does not wait on SMTP, so
    its timing says nothing about whether a message was sent.
    """
    settings = get_settings()
    # Safe to state plainly: it is the same static value for everyone and the
    # email says it anyway. Returning it keeps the UI's "expires in N minutes"
    # honest when an operator changes PASSWORD_RESET_TTL_MINUTES.
    generic = {
        "ok": True,
        "message": "If an account exists for that address, a reset link is on its way.",
        "expiresInMinutes": settings.password_reset_ttl_minutes,
    }

    result = await auth_service.request_password_reset(db, payload.email)
    if result is None:
        return generic

    email, raw_token = result
    link = f"{settings.frontend_base_url.rstrip('/')}/?reset_token={quote(raw_token)}"

    async def deliver() -> None:
        try:
            await email_service.send_password_reset(
                to=email, link=link, ttl_minutes=settings.password_reset_ttl_minutes,
            )
        except email_service.EmailError:
            # Logged, never surfaced: the caller is unauthenticated and must
            # not learn whether an address exists, let alone how mail is set up.
            logger.exception("Password reset email could not be delivered")

    background.add_task(deliver)
    return generic


@router.post("/reset-password", response_model=AuthResponse)
async def reset_password(payload: ResetPasswordRequest, db: DbSession):
    """Consumes the emailed link and returns a signed-in session -- the reset
    revoked every previous one, so the user needs a new pair either way."""
    return await auth_service.reset_password(db, payload)


# GitHub sign-in (public -- nobody is authenticated yet)
#
# The redirect back from github.com lands on the SHARED callback in
# routes/github.py, which tells this flow apart from account-linking by the
# signed state, then sends the browser to the frontend with a short-lived
# exchange code that /github/exchange trades for a real session.
@router.get("/github/authorize")
async def github_login_authorize():
    try:
        return {"url": github_service.build_login_authorize_url()}
    except github_service.GithubError as exc:
        raise api_error(503, "GITHUB_NOT_CONFIGURED", str(exc))


@router.post("/github/exchange", response_model=AuthResponse)
async def github_login_exchange(payload: GithubExchangeRequest, db: DbSession):
    claims = decode_auth_exchange_token(payload.code)
    if claims is None:
        raise api_error(401, "INVALID_EXCHANGE", "This sign-in link has expired. Please try again.")
    return await auth_service.issue_tokens_for_user(db, claims["sub"], claims["tenant_id"])


@router.post("/me/avatar", response_model=AvatarResponse)
async def upload_avatar(auth: CurrentAuth, db: DbSession, file: UploadFile = File(...)):
    user, _, _ = await auth_service.get_me(db, auth.user_id, auth.tenant_id)
    previous = user.avatar_url

    url = await avatar_service.save_avatar(auth.user_id, file)
    await auth_service.set_avatar_url(db, auth.user_id, url)
    # Only after the new one is committed, so a failed write never leaves the
    # account pointing at a file that no longer exists.
    await avatar_service.delete_avatar_file(previous)
    return AvatarResponse(avatar_url=url)


@router.delete("/me/avatar", response_model=AvatarResponse)
async def delete_avatar(auth: CurrentAuth, db: DbSession):
    user, _, _ = await auth_service.get_me(db, auth.user_id, auth.tenant_id)
    previous = user.avatar_url
    await auth_service.set_avatar_url(db, auth.user_id, None)
    await avatar_service.delete_avatar_file(previous)
    return AvatarResponse(avatar_url=None)
