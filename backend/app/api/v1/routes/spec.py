"""Specification builder: save (versioned) + confirm — separate router,
was inline in sessions/[id]/spec/route.ts on the frontend."""
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter

from app.api.deps import CurrentAuth, TenantDb
from app.core.exceptions import api_error
from app.models.message import Specification
from app.schemas.spec import SpecSave
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["spec"])


def _serialize(s: Specification) -> dict:
    return {
        "id": s.id, "sessionId": s.session_id, "version": s.version,
        "dimensions": json.loads(s.dimensions or "{}"), "isCurrent": s.is_current,
        "confirmedAt": s.confirmed_at.isoformat() if s.confirmed_at else None,
        "createdAt": s.created_at.isoformat(),
    }


@router.get("/{session_id}/spec")
async def get_spec(session_id: str, auth: CurrentAuth, db: TenantDb):
    await session_service.get_session(db, auth.tenant_id, auth.user_id, session_id)
    specs = (await db.execute(
        select(Specification).where(Specification.session_id == session_id).order_by(Specification.version.desc())
    )).scalars().all()
    current = next((s for s in specs if s.is_current), specs[0] if specs else None)
    return {"specs": [_serialize(s) for s in specs], "current": _serialize(current) if current else None}


@router.put("/{session_id}/spec")
async def save_spec(session_id: str, payload: SpecSave, auth: CurrentAuth, db: TenantDb):
    await session_service.get_session(db, auth.tenant_id, auth.user_id, session_id)

    await db.execute(
        Specification.__table__.update()
        .where(Specification.session_id == session_id, Specification.is_current.is_(True))
        .values(is_current=False)
    )
    prior = (await db.execute(
        select(Specification.version).where(Specification.session_id == session_id).order_by(Specification.version.desc())
    )).scalars().first()

    spec = Specification(
        session_id=session_id, version=(prior or 0) + 1,
        dimensions=json.dumps({k: v.model_dump(by_alias=True) for k, v in payload.dimensions.items()}),
        is_current=True,
    )
    db.add(spec)
    await db.commit()
    await db.refresh(spec)
    return {"spec": _serialize(spec)}


@router.patch("/{session_id}/spec")
async def confirm_spec(session_id: str, auth: CurrentAuth, db: TenantDb):
    await session_service.get_session(db, auth.tenant_id, auth.user_id, session_id)
    current = (await db.execute(
        select(Specification).where(Specification.session_id == session_id, Specification.is_current.is_(True))
    )).scalar_one_or_none()
    if current is None:
        raise api_error(400, "NO_SPEC", "No spec to confirm.")
    current.confirmed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current)
    return {"spec": _serialize(current)}