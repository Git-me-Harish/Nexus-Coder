from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, cuid


class GithubConnection(Base):
    """
    One row per user -- a user's own GitHub OAuth token, scoped to the tenant
    they connected it under. `encrypted_access_token` is Fernet-ciphertext
    (see app/core/crypto.py, the same mechanism ProviderCredential uses),
    never stored or returned in plaintext.

    Distinct from ProviderCredential on purpose: that table is per-tenant LLM
    API keys, shared across a tenant's users. This is a single user's own
    GitHub identity -- a different owner, a different blast radius (this
    token can create repos and push code under that person's account), and a
    different real-world lifecycle (a user revoking the OAuth grant on
    github.com should not silently affect anyone else's LLM access).
    """
    __tablename__ = "github_connections"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_github_connection"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=cuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    encrypted_access_token: Mapped[str] = mapped_column(String, nullable=False)
    github_login: Mapped[str] = mapped_column(String, nullable=False)
    github_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
