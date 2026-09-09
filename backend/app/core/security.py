""" Auth primitives: JWT access/refresh tokens (PyJWT) + Argon2id password hashing """
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

settings = get_settings()

_ph = PasswordHasher(
    time_cost=3,        # iterations
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
    GITHUB_OAUTH_STATE = "github_oauth_state"
    GITHUB_LOGIN_STATE = "github_login_state"
    AUTH_EXCHANGE = "auth_exchange"
    PREVIEW_ACCESS = "preview_access"
    SUDO = "sudo"


# Password hashing 
def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return _ph.verify(stored_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        # Malformed hash, unknown algo, etc. — never raise into a 500,
        # always treat as invalid credentials.
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _ph.check_needs_rehash(stored_hash)


# JWT access tokens 
def create_access_token(*, user_id: str, tenant_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "email": email,
        "type": TokenType.ACCESS.value,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
        "iss": "nexus-api",
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer="nexus-api",
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != TokenType.ACCESS.value:
        return None
    return payload


# GitHub OAuth CSRF state
#
# A signed, short-lived JWT standing in for the `state` param GitHub's OAuth
# flow requires. Reuses the same secret/algorithm as access tokens rather
# than adding a Redis/DB-backed state table -- the state token is opaque to
# GitHub and round-trips through the redirect unmodified, so a JWT's normal
# statelessness is exactly what's needed here: the callback can validate it
# without a lookup, and a stolen callback URL is useless after 10 minutes.
def create_github_oauth_state(*, user_id: str, tenant_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id, "tenant_id": tenant_id,
        "type": TokenType.GITHUB_OAUTH_STATE.value,
        "iat": now, "exp": now + timedelta(minutes=10),
        "iss": "nexus-api", "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_github_oauth_state(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm],
            issuer="nexus-api", options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != TokenType.GITHUB_OAUTH_STATE.value:
        return None
    return payload


# GitHub SIGN-IN state
#
# Same mechanism as the connect state above, but for the flow where NOBODY is
# signed in yet -- "Continue with GitHub" on the login screen. There is no
# user_id to bind to, so `sub` is just a random nonce; the token's whole job
# is proving the callback's `state` came from us (CSRF) and telling the
# shared callback route which of the two flows it is servicing.
def create_github_login_state() -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": secrets.token_hex(16),
        "type": TokenType.GITHUB_LOGIN_STATE.value,
        "iat": now, "exp": now + timedelta(minutes=10),
        "iss": "nexus-api", "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_github_login_state(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm],
            issuer="nexus-api", options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != TokenType.GITHUB_LOGIN_STATE.value:
        return None
    return payload


# Short-lived auth exchange code
#
# The GitHub sign-in callback is a bare browser redirect, so the only way to
# hand the frontend a session is through the URL -- and putting real access
# and refresh tokens in a URL leaks them into browser history, the Referer
# header, and any logging proxy in between. Instead the callback mints one of
# these (2 minutes, identity only, useless as an API credential because every
# authenticated route rejects a non-"access" token type) and the frontend
# immediately POSTs it to /auth/github/exchange for the real token pair.
#
# Stated plainly rather than implied: this is short-lived, NOT single-use.
# Nothing records that a code was redeemed, so within its 2-minute window the
# same code would mint a second session. Making it truly one-shot needs
# server-side state for spent jtis (Redis, or a table) -- worth doing if these
# codes ever travel further than one same-tab redirect.
def create_auth_exchange_token(*, user_id: str, tenant_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id, "tenant_id": tenant_id,
        "type": TokenType.AUTH_EXCHANGE.value,
        "iat": now, "exp": now + timedelta(minutes=2),
        "iss": "nexus-api", "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_auth_exchange_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm],
            issuer="nexus-api", options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != TokenType.AUTH_EXCHANGE.value:
        return None
    return payload


# Step-up ("sudo") elevation
#
# Being signed in is not the same as having just PROVEN you are the account
# owner. A stolen laptop, a borrowed session, an XSS-lifted access token --
# all of them satisfy the normal bearer check. Managing provider API keys is
# the kind of action that deserves a fresh proof, so those routes require one
# of these ON TOP of the usual access token (see app/api/deps.RequireSudo).
#
# Deliberately a SEPARATE token rather than a claim added to the access token:
# the access token is persisted to localStorage by the frontend's auth store,
# so an elevation baked into it would survive reloads and quietly become
# permanent. This one is held in memory only and dies with the tab, which is
# the entire point of step-up auth.
def create_sudo_token(*, user_id: str, tenant_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id, "tenant_id": tenant_id,
        "type": TokenType.SUDO.value,
        "iat": now, "exp": now + timedelta(minutes=settings.sudo_ttl_minutes),
        "iss": "nexus-api", "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_sudo_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm],
            issuer="nexus-api", options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != TokenType.SUDO.value:
        return None
    return payload


# Preview proxy access
#
# A bare `<iframe src>` cannot carry an Authorization header the way a
# fetch() call can -- there is no hook to attach one to a plain browser
# navigation. So the live-preview proxy route (app/api/v1/routes/preview.py)
# cannot use the normal CurrentAuth bearer-token dependency; instead
# POST /sessions/{id}/preview/start mints one of these, scoped to exactly
# that session, and the frontend embeds it in the iframe's src as a query
# param. The proxy route validates this signed token itself rather than
# accepting an ambient cookie or trusting the path's session_id alone.
def create_preview_access_token(*, session_id: str, user_id: str, tenant_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id, "tenant_id": tenant_id, "session_id": session_id,
        "type": TokenType.PREVIEW_ACCESS.value,
        "iat": now, "exp": now + timedelta(hours=2),
        "iss": "nexus-api", "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_preview_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm],
            issuer="nexus-api", options={"require": ["exp", "iat", "sub", "session_id"]},
        )
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != TokenType.PREVIEW_ACCESS.value:
        return None
    return payload


# Opaque refresh tokens
def generate_refresh_token() -> tuple[str, str]:
    """Returns (raw_token_to_send_to_client, sha256_hash_to_store_in_db)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# Password reset tokens
#
# Opaque and random rather than a JWT, because unlike the OAuth exchange code
# this one MUST be revocable and single-use: it lives in an inbox for up to
# half an hour. That state lives in the password_reset_tokens table, and only
# the hash is stored there -- same reasoning as refresh tokens above.
def generate_password_reset_token() -> tuple[str, str]:
    """Returns (raw_token_for_the_email_link, sha256_hash_to_store_in_db)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_password_reset_token(raw)


def hash_password_reset_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_token_family() -> str:
    return secrets.token_hex(16)