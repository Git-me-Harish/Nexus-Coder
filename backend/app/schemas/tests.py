from pydantic import Field

from app.schemas.base import CamelModel


class UserTestCaseCreate(CamelModel):
    """A test case the user writes themselves during Debug, to be run for
    real in the sandbox alongside whatever the agent has already written --
    see app/api/v1/routes/tests.py."""
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=20_000)


class UserTestCaseResult(CamelModel):
    file_path: str
    passed: bool
    exit_code: int
    output: str
