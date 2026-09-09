"""
User-authored test cases -- the Debug phase's "you can write test cases too"
affordance.

Reuses 100% of the existing execution plumbing: `workspace.write_file` for
the file, `run_in_sandbox` for the real run, `sync_from_disk` to reconcile
whatever the run touched back into the DB. No new execution path -- a
user-submitted test runs in exactly the same offline, non-root, read-only-
rootfs container the agent's own `run_command` tool uses (see
app/agents/sandbox.py), so the security posture doesn't get a second,
possibly-weaker copy.
"""
import re

from fastapi import APIRouter

from app.agents import workspace
from app.agents.sandbox import run_in_sandbox
from app.api.deps import CurrentAuth, TenantDb
from app.core.exceptions import api_error
from app.schemas.tests import UserTestCaseCreate, UserTestCaseResult
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["tests"])

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(name: str) -> str:
    slug = _SLUG_RE.sub("_", name.strip().lower()).strip("_")
    return slug or "case"


@router.post("/{session_id}/tests")
async def run_user_test_case(session_id: str, payload: UserTestCaseCreate, auth: CurrentAuth, db: TenantDb):
    session = await session_service.get_session(db, auth.tenant_id, auth.user_id, session_id)

    # The container only sees what's on disk; a session that has never had a
    # command run against it (or was restored on a different machine) may
    # have files that exist only in Postgres.
    await workspace.hydrate_from_db(db, session.id)

    file_path = f"tests/test_user_{_slug(payload.name)}.py"
    await workspace.write_file(session.id, file_path, payload.code)

    result = await run_in_sandbox(f"python -m pytest -q {file_path}", workspace.workspace_root(session.id))
    if result.error:
        raise api_error(503, "SANDBOX_UNAVAILABLE", result.error)

    await workspace.sync_from_disk(db, session.id)
    await db.commit()

    return {
        "result": UserTestCaseResult(
            file_path=file_path, passed=result.exit_code == 0,
            exit_code=result.exit_code, output=result.output,
        ).model_dump(by_alias=True)
    }
