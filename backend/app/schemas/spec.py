from datetime import datetime
from typing import Any

from app.schemas.base import CamelModel


class SpecSave(CamelModel):
    dimensions: dict[str, Any]


class SpecConfirm(CamelModel):
    action: str = "confirm"


class SpecOut(CamelModel):
    id: str
    session_id: str
    version: int
    dimensions: dict[str, Any]
    is_current: bool
    confirmed_at: datetime | None
    created_at: datetime
