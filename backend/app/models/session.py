from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, cuid


class AgentSession(Base, TimestampMixin):
    """
    Named AgentSession (not Session) to avoid clashing with SQLAlchemy's
    own Session class in imports throughout the codebase.
    """
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=cuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))

    mode: Mapped[str] = mapped_column(String, nullable=False)  # development|problem_solving|learning
    current_phase: Mapped[str] = mapped_column(String, default="ideation")
    base_model_id: Mapped[str] = mapped_column(String, default="claude-sonnet-4-6")
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    tokens_budget: Mapped[int] = mapped_column(Integer, default=500_000)
    status: Mapped[str] = mapped_column(String, default="active")  # active|paused|completed|failed
    starred: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)

    langgraph_thread_id: Mapped[str | None] = mapped_column(String, nullable=True)
    sandbox_status: Mapped[str] = mapped_column(String, default="none")
    sandbox_preview_url: Mapped[str | None] = mapped_column(String, nullable=True)
    github_repo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_doc_url: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    specifications: Mapped[list["Specification"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    files: Mapped[list["SessionFile"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    tasks: Mapped[list["AgentTask"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    learning_topics: Mapped[list["LearningTopic"]] = relationship(back_populates="session", cascade="all, delete-orphan")
