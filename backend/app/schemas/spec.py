"""
Spec-builder payloads.

`dimensions` was previously typed `dict[str, Any]`, which meant two things
were quietly broken at once: nothing validated the dimension slugs (so a
typo'd or invented slug was persisted as though it were real), and the save
route called `.model_dump()` on values that were plain dicts, so every save
raised AttributeError before it could write anything. The typed model below
is what constants.SPEC_DIMENSION_SLUGS was added for -- see the note there
about keeping the list in sync with the frontend's dimension catalog.
"""
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, field_validator

from app.agents.constants import SPEC_DIMENSION_SLUGS
from app.schemas.base import CamelModel


class SpecDimension(CamelModel):
    """One chosen option for one spec dimension. The frontend owns the full
    option catalog (labels, descriptions, curated choices), so extra keys are
    preserved rather than rejected -- the backend only needs the identity of
    the choice, and dropping the rest would silently lose data the UI renders."""

    model_config = ConfigDict(
        alias_generator=CamelModel.model_config["alias_generator"],
        populate_by_name=True,
        from_attributes=True,
        extra="allow",
    )

    id: str
    label: str


class SpecSave(CamelModel):
    dimensions: dict[str, SpecDimension]

    @field_validator("dimensions")
    @classmethod
    def _reject_unknown_slugs(cls, value: dict[str, SpecDimension]) -> dict[str, SpecDimension]:
        unknown = sorted(set(value) - set(SPEC_DIMENSION_SLUGS))
        if unknown:
            raise ValueError(
                f"Unknown spec dimension(s): {', '.join(unknown)}. "
                f"Valid dimensions: {', '.join(SPEC_DIMENSION_SLUGS)}"
            )
        return value


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
