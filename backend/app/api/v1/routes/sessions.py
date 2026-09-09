from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import CurrentAuth, TenantDb
from app.models.message import Message, SessionFile, Specification
from app.models.learning import LearningTopic
from app.models.project import Project
from app.schemas.project import ProjectOut
from app.schemas.session import AdvancePhaseRequest, SessionCreate, SessionOut, SessionUpdate, SwitchModelRequest
from app.schemas.session import MessageOut
from app.schemas.learning import LearningTopicOut
from app.services import session_service
import json

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(auth: CurrentAuth, db: TenantDb, project_id: str | None = Query(default=None, alias="projectId")):
    sessions = await session_service.list_sessions(db, auth.tenant_id, auth.user_id, project_id)
    return {"sessions": [SessionOut.model_validate(s) for s in sessions]}


@router.post("", status_code=201)
async def create_session(payload: SessionCreate, auth: CurrentAuth, db: TenantDb):
    session = await session_service.create_session(db, auth.tenant_id, auth.user_id, payload)
    return {"session": SessionOut.model_validate(session)}


@router.get("/{session_id}")
async def get_session(session_id: str, auth: CurrentAuth, db: TenantDb):
    session = await session_service.get_session(db, auth.tenant_id, auth.user_id, session_id)

    messages = (await db.execute(select(Message).where(Message.session_id == session_id).order_by(Message.created_at.asc()))).scalars().all()
    files = (await db.execute(select(SessionFile).where(SessionFile.session_id == session_id))).scalars().all()
    specs = (await db.execute(select(Specification).where(Specification.session_id == session_id).order_by(Specification.version.desc()))).scalars().all()
    topics = (await db.execute(select(LearningTopic).where(LearningTopic.session_id == session_id).order_by(LearningTopic.started_at.desc()))).scalars().all()
    project = await db.get(Project, session.project_id)

    body = SessionOut.model_validate(session).model_dump(by_alias=True)
    body["messages"] = [MessageOut.model_validate(m).model_dump(by_alias=True) for m in messages]
    body["files"] = [{"id": f.id, "filePath": f.file_path, "language": f.language, "version": f.version} for f in files]
    body["specifications"] = [
        {
            "id": s.id, "sessionId": s.session_id, "version": s.version,
            "dimensions": json.loads(s.dimensions or "{}"), "isCurrent": s.is_current,
            "confirmedAt": s.confirmed_at.isoformat() if s.confirmed_at else None,
            "createdAt": s.created_at.isoformat(),
        }
        for s in specs
    ]
    body["learningTopics"] = [LearningTopicOut.model_validate(t).model_dump(by_alias=True) for t in topics]
    body["project"] = ProjectOut.model_validate(project).model_dump(by_alias=True) if project else None

    return {"session": body}


@router.post("/{session_id}")
async def advance_phase(session_id: str, payload: AdvancePhaseRequest, auth: CurrentAuth, db: TenantDb):
    session = await session_service.advance_phase(db, auth.tenant_id, auth.user_id, session_id, payload.target)
    return {"session": SessionOut.model_validate(session)}


@router.patch("/{session_id}")
async def update_session(session_id: str, payload: SessionUpdate, auth: CurrentAuth, db: TenantDb):
    session = await session_service.update_session(db, auth.tenant_id, auth.user_id, session_id, payload)
    return {"session": SessionOut.model_validate(session)}


@router.delete("/{session_id}")
async def delete_session(session_id: str, auth: CurrentAuth, db: TenantDb):
    await session_service.delete_session(db, auth.tenant_id, auth.user_id, session_id)
    return {"ok": True}


@router.post("/{session_id}/model")
async def switch_model(session_id: str, payload: SwitchModelRequest, auth: CurrentAuth, db: TenantDb):
    session, previous = await session_service.switch_model(db, auth.tenant_id, auth.user_id, session_id, payload.model_id)
    return {"session": SessionOut.model_validate(session), "from": previous, "to": payload.model_id}


@router.patch("/{session_id}/idea/confirm")
async def confirm_idea(session_id: str, auth: CurrentAuth, db: TenantDb):
    """Confirms IDEA.md (written by the agent via write_file during Ideation)
    as ground truth for Planning. See session_service.confirm_idea."""
    session = await session_service.confirm_idea(db, auth.tenant_id, auth.user_id, session_id)
    return {"session": SessionOut.model_validate(session)}


@router.patch("/{session_id}/plan/confirm")
async def confirm_plan(session_id: str, auth: CurrentAuth, db: TenantDb):
    """Confirms PLAN.md as ground truth for Specification. See
    session_service.confirm_plan."""
    session = await session_service.confirm_plan(db, auth.tenant_id, auth.user_id, session_id)
    return {"session": SessionOut.model_validate(session)}