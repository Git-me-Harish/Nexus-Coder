import io
import re
import zipfile

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.agents import workspace
from app.api.deps import CurrentAuth, TenantDb
from app.models.message import SessionFile
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["files"])


@router.get("/{session_id}/files")
async def list_files(session_id: str, auth: CurrentAuth, db: TenantDb):
    await session_service.get_session(db, auth.tenant_id, auth.user_id, session_id)
    files = (await db.execute(
        select(SessionFile).where(SessionFile.session_id == session_id).order_by(SessionFile.file_path.asc())
    )).scalars().all()
    return {"files": [
        {"id": f.id, "filePath": f.file_path, "content": f.content, "language": f.language, "version": f.version}
        for f in files
    ]}


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@router.get("/{session_id}/export/zip")
async def export_zip(session_id: str, auth: CurrentAuth, db: TenantDb):
    """
    Downloads the session workspace as a zip.

    Calls hydrate_from_db first so a session that was restored on a
    different machine (or never had a command run against it, so nothing
    ever materialized the DB rows onto this disk) still exports the latest
    state -- the DB is the durable record, the workspace directory is a
    working copy that may be stale or missing entirely. Excludes the same
    IGNORED_DIRS workspace.py already excludes from sync (.git,
    node_modules, __pycache__, ...) -- churn nobody wants in a downloaded zip.
    """
    session = await session_service.get_session(db, auth.tenant_id, auth.user_id, session_id)
    await workspace.hydrate_from_db(db, session.id)

    entries = workspace.list_workspace_files(session.id)
    root = workspace.workspace_root(session.id)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry in entries:
            zf.write(root / entry["path"], arcname=entry["path"])
    buffer.seek(0)

    safe_title = _SAFE_NAME_RE.sub("-", session.title or "nexus-project").strip("-") or "nexus-project"
    filename = f"{safe_title}-{session.id[:8]}.zip"

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )