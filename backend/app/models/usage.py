from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, DateTime, func, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, cuid


class TokenUsageLedger(Base):
    """
    Append-only ledger — one row per billable model call. Aggregate via
    query, never mutate in place. This is what usage/billing rollups
    (Celery job) read from; it's also the audit trail for token-budget
    enforcement per session/tenant.
    """
    __tablename__ = "token_usage_ledger"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=cuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
