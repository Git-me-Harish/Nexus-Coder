from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
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
    # Column default is a literal on purpose: it is baked into migrations, so
    # it must not silently change when the catalog's DEFAULT_MODEL_ID moves.
    # session_service always passes an explicit id, so this only applies to
    # rows inserted outside that path.
    base_model_id: Mapped[str] = mapped_column(String, default="claude-sonnet-5")
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

    # Confirmation gates for the artifact-producing phases, mirroring
    # Specification.confirmed_at (app/models/message.py) exactly -- ideation
    # and planning each write a workspace file (IDEA.md / PLAN.md) via the
    # agent's own write_file tool rather than a dedicated table, and these
    # timestamps are what session_service.advance_phase checks before
    # letting the session move past them. See constants.APPROVAL_REQUIRED_TRANSITIONS.
    idea_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plan_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Set once, by the user, at the start of Implementation -- deliberately
    # NOT inferred from a free-text reply (see build_depth gate in the route
    # layer): "prototype" | "mvp" | "production". Threaded into
    # build_context_digest so the implementation prompt can adapt scope.
    build_depth: Mapped[str | None] = mapped_column(String, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    specifications: Mapped[list["Specification"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    files: Mapped[list["SessionFile"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    tasks: Mapped[list["AgentTask"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    learning_topics: Mapped[list["LearningTopic"]] = relationship(back_populates="session", cascade="all, delete-orphan")
