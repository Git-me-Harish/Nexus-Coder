from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, cuid


class LearningTopic(Base):
    """
    Stage machine: explain -> practice -> quiz -> completed (see
    app/agents/learning_engine.py:next_stage). One row per attempt — a
    topic can be restarted, producing a new row with attempts accumulating
    via the UserKnowledgeProfile rolling average, not this row.
    """
    __tablename__ = "learning_topics"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=cuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_slug: Mapped[str] = mapped_column(String, nullable=False)
    topic_label: Mapped[str] = mapped_column(String, nullable=False)
    stage: Mapped[str] = mapped_column(String, default="explain")  # explain|practice|quiz|completed
    difficulty: Mapped[str] = mapped_column(String, default="intermediate")  # beginner|intermediate|advanced
    quiz_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["AgentSession"] = relationship(back_populates="learning_topics")


class UserKnowledgeProfile(Base):
    __tablename__ = "user_knowledge_profiles"
    __table_args__ = (UniqueConstraint("user_id", "topic_slug", name="uq_user_topic"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=cuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_slug: Mapped[str] = mapped_column(String, index=True, nullable=False)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
