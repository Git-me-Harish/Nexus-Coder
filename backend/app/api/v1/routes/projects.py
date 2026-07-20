from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentAuth, TenantDb
from app.models.user import TenantMember
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
async def list_projects(auth: CurrentAuth, db: TenantDb):
    projects = await project_service.list_projects(db, auth.tenant_id)
    return {"projects": [ProjectOut.model_validate(p) for p in projects]}


@router.post("", status_code=201)
async def create_project(payload: ProjectCreate, auth: CurrentAuth, db: TenantDb):
    project = await project_service.create_project(db, auth.tenant_id, auth.user_id, payload)
    return {"project": ProjectOut.model_validate(project)}


@router.patch("/{project_id}")
async def update_project(project_id: str, payload: ProjectUpdate, auth: CurrentAuth, db: TenantDb):
    project = await project_service.update_project(db, auth.tenant_id, project_id, payload)
    return {"project": ProjectOut.model_validate(project)}


@router.delete("/{project_id}")
async def delete_project(project_id: str, auth: CurrentAuth, db: TenantDb):
    membership = (await db.execute(
        select(TenantMember).where(TenantMember.tenant_id == auth.tenant_id, TenantMember.user_id == auth.user_id)
    )).scalar_one_or_none()
    role = membership.role if membership else "member"
    await project_service.delete_project(db, auth.tenant_id, auth.user_id, role, project_id)
    return {"ok": True}