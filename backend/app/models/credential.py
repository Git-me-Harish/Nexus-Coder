from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, cuid


class ProviderCredential(Base):
    """
    One row per (tenant, provider) -- a tenant can configure at most one
    key per provider. `encrypted_api_key` is Fernet-ciphertext (see
    app/core/crypto.py), never plaintext. `key_preview` is safe to store
    and return as-is (e.g. "sk-ant-...wXyZ") -- not enough to reconstruct
    the key, purely for the user to recognize which key is saved.
    """
    __tablename__ = "provider_credentials"
    __table_args__ = (UniqueConstraint("tenant_id", "provider", name="uq_tenant_provider_credential"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=cuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String, nullable=False)  # anthropic | openai
    encrypted_api_key: Mapped[str] = mapped_column(String, nullable=False)
    key_preview: Mapped[str] = mapped_column(String, nullable=False)
    is_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # null = never validated
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_validation_error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())