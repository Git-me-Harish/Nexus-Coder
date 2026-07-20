from datetime import datetime

from pydantic import Field

from app.schemas.base import CamelModel


class ProjectCreate(CamelModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    mode: str = "development"


class ProjectUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = None
    starred: bool | None = None
    pinned: bool | None = None


class ProjectOut(CamelModel):
    id: str
    tenant_id: str
    created_by: str
    name: str
    description: str | None
    mode: str
    status: str
    starred: bool
    pinned: bool
    created_at: datetime
    updated_at: datetime