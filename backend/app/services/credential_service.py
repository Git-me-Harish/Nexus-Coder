"""
BYOK (bring-your-own-key) credential management. A tenant configures their
own provider API keys here; models become usable for that tenant once a
valid key exists -- either their own, or (optionally) a platform-wide
fallback key from settings (see config.py's comment on why that's opt-in).

Validation calls each provider's cheapest possible endpoint (a model list,
not a completion) so checking a key doesn't spend the user's own credits.
"""
from datetime import datetime, timezone

import anthropic
import openai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import decrypt_secret, encrypt_secret, mask_key
from app.core.exceptions import api_error
from app.models.credential import ProviderCredential
from app.schemas.credential import CredentialOut, ValidationResult

settings = get_settings()

SUPPORTED_PROVIDERS = ["anthropic", "openai", "groq", "gemini"]


async def validate_key(provider: str, api_key: str) -> ValidationResult:
    """Live-checks a key against the provider's cheapest endpoint. Never
    raises -- failures come back as a ValidationResult, since a bad key is
    an expected user input, not a server error."""
    try:
        if provider == "anthropic":
            await anthropic.AsyncAnthropic(api_key=api_key).models.list(limit=1)
        elif provider == "openai":
            await openai.AsyncOpenAI(api_key=api_key).models.list()
        elif provider == "groq":
            from app.agents.providers.groq_provider import GROQ_BASE_URL
            await openai.AsyncOpenAI(api_key=api_key, base_url=GROQ_BASE_URL).models.list()
        elif provider == "gemini":
            from google import genai
            from google.genai import errors as genai_errors
            try:
                await genai.Client(api_key=api_key).aio.models.list(config={"page_size": 1})
            except genai_errors.ClientError as exc:
                if exc.code in (401, 403):
                    return ValidationResult(provider=provider, is_valid=False, error="Invalid API key")
                return ValidationResult(provider=provider, is_valid=False, error=f"Could not verify key: {exc}")
        else:
            return ValidationResult(provider=provider, is_valid=False, error="Unsupported provider")
        return ValidationResult(provider=provider, is_valid=True)
    except (anthropic.AuthenticationError, openai.AuthenticationError):
        return ValidationResult(provider=provider, is_valid=False, error="Invalid API key")
    except (anthropic.APIError, openai.APIError) as exc:
        # Rate-limited, transient outage, etc. -- key might be fine, we
        # just couldn't confirm it right now. Distinct from "invalid".
        return ValidationResult(provider=provider, is_valid=False, error=f"Could not verify key: {exc}")
    except Exception as exc:
        return ValidationResult(provider=provider, is_valid=False, error=f"Unexpected error: {exc}")


async def save_credential(db: AsyncSession, tenant_id: str, user_id: str, provider: str, api_key: str) -> CredentialOut:
    if provider not in SUPPORTED_PROVIDERS:
        raise api_error(400, "UNSUPPORTED_PROVIDER", f"'{provider}' is not a supported provider.")

    result = await validate_key(provider, api_key)

    existing = (await db.execute(
        select(ProviderCredential).where(
            ProviderCredential.tenant_id == tenant_id, ProviderCredential.provider == provider
        )
    )).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if existing:
        existing.encrypted_api_key = encrypt_secret(api_key)
        existing.key_preview = mask_key(api_key)
        existing.is_valid = result.is_valid
        existing.last_validated_at = now
        existing.last_validation_error = result.error
        row = existing
    else:
        row = ProviderCredential(
            tenant_id=tenant_id, created_by=user_id, provider=provider,
            encrypted_api_key=encrypt_secret(api_key), key_preview=mask_key(api_key),
            is_valid=result.is_valid, last_validated_at=now, last_validation_error=result.error,
        )
        db.add(row)

    await db.commit()
    await db.refresh(row)
    return CredentialOut.model_validate(row)


async def list_credentials(db: AsyncSession, tenant_id: str) -> list[CredentialOut]:
    result = await db.execute(select(ProviderCredential).where(ProviderCredential.tenant_id == tenant_id))
    return [CredentialOut.model_validate(row) for row in result.scalars().all()]


async def delete_credential(db: AsyncSession, tenant_id: str, provider: str) -> None:
    row = (await db.execute(
        select(ProviderCredential).where(
            ProviderCredential.tenant_id == tenant_id, ProviderCredential.provider == provider
        )
    )).scalar_one_or_none()
    if row is None:
        raise api_error(404, "NOT_FOUND", f"No {provider} credential configured.")
    await db.delete(row)
    await db.commit()


async def revalidate_credential(db: AsyncSession, tenant_id: str, provider: str) -> CredentialOut:
    row = (await db.execute(
        select(ProviderCredential).where(
            ProviderCredential.tenant_id == tenant_id, ProviderCredential.provider == provider
        )
    )).scalar_one_or_none()
    if row is None:
        raise api_error(404, "NOT_FOUND", f"No {provider} credential configured.")

    api_key = decrypt_secret(row.encrypted_api_key)
    result = await validate_key(provider, api_key)
    row.is_valid = result.is_valid
    row.last_validated_at = datetime.now(timezone.utc)
    row.last_validation_error = result.error
    await db.commit()
    await db.refresh(row)
    return CredentialOut.model_validate(row)


async def resolve_api_key(db: AsyncSession, tenant_id: str, provider: str) -> str | None:
    """
    Resolution order: tenant's own valid key first, then the platform
    fallback key from settings (if configured -- see config.py). Returns
    None if neither exists, which the caller (provider router) turns into
    a ProviderNotConfiguredError with an actionable message rather than a
    generic failure.
    """
    row = (await db.execute(
        select(ProviderCredential).where(
            ProviderCredential.tenant_id == tenant_id, ProviderCredential.provider == provider
        )
    )).scalar_one_or_none()
    if row is not None and row.is_valid is not False:
        return decrypt_secret(row.encrypted_api_key)

    platform_key = {
        "anthropic": settings.anthropic_api_key, "openai": settings.openai_api_key,
        "groq": settings.groq_api_key, "gemini": settings.gemini_api_key,
    }.get(provider)
    return platform_key


async def tenant_has_usable_key(db: AsyncSession, tenant_id: str, provider: str) -> bool:
    key = await resolve_api_key(db, tenant_id, provider)
    return key is not None