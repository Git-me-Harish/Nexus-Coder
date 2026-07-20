from datetime import datetime

from pydantic import Field

from app.schemas.base import CamelModel


class CredentialSave(CamelModel):
    api_key: str = Field(min_length=8, max_length=500)


class CredentialOut(CamelModel):
    """Never includes the actual key -- key_preview is display-only and
    cannot reconstruct it."""
    provider: str
    key_preview: str
    is_valid: bool | None
    last_validated_at: datetime | None
    last_validation_error: str | None
    updated_at: datetime


class ValidationResult(CamelModel):
    provider: str
    is_valid: bool
    error: str | None = None