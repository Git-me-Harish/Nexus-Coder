from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.constants import PHASE_ROUTING, get_model, initial_phase_for_mode, next_phase, requires_approval
from app.core.exceptions import api_error
from app.models.message import Message, Specification
from app.models.project import Project
from app.models.session import AgentSession
from app.schemas.session import SessionCreate, SessionUpdate


async def create_session(db: AsyncSession, tenant_id: str, user_id: str, payload: SessionCreate) -> AgentSession:
    project = (await db.execute(
        select(Project).where(Project.id == payload.project_id, Project.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if project is None:
        raise api_error(404, "PROJECT_NOT_FOUND")

    initial_phase = initial_phase_for_mode(payload.mode)
    session = AgentSession(
        project_id=payload.project_id, tenant_id=tenant_id, user_id=user_id,
        mode=payload.mode, current_phase=initial_phase,
        base_model_id=payload.base_model_id or PHASE_ROUTING.get(initial_phase, "claude-sonnet-4-6"),
        tokens_budget=500_000, title=payload.title or f"New {payload.mode} session",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, tenant_id: str, user_id: str, session_id: str) -> AgentSession:
    result = await db.execute(
        select(AgentSession).where(
            AgentSession.id == session_id, AgentSession.tenant_id == tenant_id, AgentSession.user_id == user_id
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise api_error(404, "NOT_FOUND")
    return session


async def list_sessions(db: AsyncSession, tenant_id: str, user_id: str, project_id: str | None = None) -> list[AgentSession]:
    stmt = select(AgentSession).where(AgentSession.tenant_id == tenant_id, AgentSession.user_id == user_id)
    if project_id:
        stmt = stmt.where(AgentSession.project_id == project_id)
    result = await db.execute(stmt.order_by(AgentSession.updated_at.desc()))
    return list(result.scalars().all())


async def update_session(db: AsyncSession, tenant_id: str, user_id: str, session_id: str, payload: SessionUpdate) -> AgentSession:
    session = await get_session(db, tenant_id, user_id, session_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(session, field, value)
    await db.commit()
    await db.refresh(session)
    return session


async def delete_session(db: AsyncSession, tenant_id: str, user_id: str, session_id: str) -> None:
    session = await get_session(db, tenant_id, user_id, session_id)
    await db.delete(session)
    await db.commit()


async def advance_phase(db: AsyncSession, tenant_id: str, user_id: str, session_id: str, target: str | None) -> AgentSession:
    session = await get_session(db, tenant_id, user_id, session_id)
    resolved_target = target or next_phase(session.current_phase)
    if not resolved_target:
        raise api_error(400, "NO_NEXT_PHASE")

    if requires_approval(session.current_phase, resolved_target):
        spec = (await db.execute(
            select(Specification).where(Specification.session_id == session.id, Specification.is_current.is_(True))
        )).scalar_one_or_none()
        if not spec or not spec.confirmed_at:
            raise api_error(
                409, "SPEC_NOT_CONFIRMED",
                "Specification must be confirmed before the Implementation phase can begin.",
            )

    session.current_phase = resolved_target
    await db.commit()
    await db.refresh(session)
    return session


async def switch_model(db: AsyncSession, tenant_id: str, user_id: str, session_id: str, model_id: str) -> tuple[AgentSession, str]:
    session = await get_session(db, tenant_id, user_id, session_id)
    model = get_model(model_id)
    if not model or not model.get("available"):
        raise api_error(400, "MODEL_UNAVAILABLE")
    previous = session.base_model_id
    session.base_model_id = model_id
    await db.commit()
    await db.refresh(session)
    return session, previous


async def list_messages(db: AsyncSession, tenant_id: str, user_id: str, session_id: str) -> list[Message]:
    await get_session(db, tenant_id, user_id, session_id)
    result = await db.execute(select(Message).where(Message.session_id == session_id).order_by(Message.created_at.asc()))
    return list(result.scalars().all())


async def check_token_budget(session: AgentSession) -> None:
    if session.tokens_used >= session.tokens_budget:
        raise api_error(402, "TOKEN_BUDGET_EXHAUSTED", f"Session token budget exhausted ({session.tokens_used}/{session.tokens_budget})")