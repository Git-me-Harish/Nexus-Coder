from datetime import datetime

from pydantic import Field

from app.schemas.base import CamelModel


class SessionCreate(CamelModel):
    project_id: str = Field(min_length=1)
    mode: str = Field(pattern="^(development|problem_solving|learning)$")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    base_model_id: str | None = Field(default=None, min_length=1, max_length=100)


class SessionUpdate(CamelModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    starred: bool | None = None
    pinned: bool | None = None
    status: str | None = None


class AdvancePhaseRequest(CamelModel):
    target: str | None = None


class SessionOut(CamelModel):
    id: str
    project_id: str
    tenant_id: str
    user_id: str
    mode: str
    current_phase: str
    base_model_id: str
    tokens_used: int
    tokens_budget: int
    status: str
    starred: bool
    pinned: bool
    title: str | None
    sandbox_status: str
    sandbox_preview_url: str | None
    created_at: datetime
    updated_at: datetime


class MessageOut(CamelModel):
    id: str
    role: str
    content: str
    phase: str | None
    model_id: str | None
    created_at: datetime


class SwitchModelRequest(CamelModel):
    model_id: str = Field(min_length=1, max_length=100)


class SendMessageRequest(CamelModel):
    content: str = Field(min_length=1, max_length=32_000)


class StreamMessageRequest(CamelModel):
    user_message: str = Field(min_length=1, max_length=32_000)