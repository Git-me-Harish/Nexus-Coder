from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentAuth, TenantDb
from app.models.message import SessionFile
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["files"])


@router.get("/{session_id}/files")
async def list_files(session_id: str, auth: CurrentAuth, db: TenantDb):
    await session_service.get_session(db, auth.tenant_id, session_id)
    files = (await db.execute(
        select(SessionFile).where(SessionFile.session_id == session_id).order_by(SessionFile.file_path.asc())
    )).scalars().all()
    return {"files": [
        {"id": f.id, "filePath": f.file_path, "content": f.content, "language": f.language, "version": f.version}
        for f in files
    ]}