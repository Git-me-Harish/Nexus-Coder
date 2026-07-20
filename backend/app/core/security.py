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


# Opaque refresh tokens 
def generate_refresh_token() -> tuple[str, str]:
    """Returns (raw_token_to_send_to_client, sha256_hash_to_store_in_db)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_token_family() -> str:
    return secrets.token_hex(16)