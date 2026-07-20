from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import api_error
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


async def list_projects(db: AsyncSession, tenant_id: str) -> list[Project]:
    result = await db.execute(
        select(Project).where(Project.tenant_id == tenant_id, Project.status == "active")
        .order_by(Project.updated_at.desc())
    )
    return list(result.scalars().all())


async def create_project(db: AsyncSession, tenant_id: str, user_id: str, payload: ProjectCreate) -> Project:
    project = Project(tenant_id=tenant_id, created_by=user_id, **payload.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def get_project(db: AsyncSession, tenant_id: str, project_id: str) -> Project:
    """tenant_id is always part of the WHERE clause — app-layer half of
    tenant isolation (Postgres RLS is the other half, see alembic/versions).
    A project_id from another tenant returns 404, never 403."""
    result = await db.execute(select(Project).where(Project.id == project_id, Project.tenant_id == tenant_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise api_error(404, "NOT_FOUND")
    return project


async def update_project(db: AsyncSession, tenant_id: str, project_id: str, payload: ProjectUpdate) -> Project:
    project = await get_project(db, tenant_id, project_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, tenant_id: str, user_id: str, user_role: str, project_id: str) -> None:
    project = await get_project(db, tenant_id, project_id)
    if user_role not in ("owner", "admin") and project.created_by != user_id:
        raise api_error(403, "FORBIDDEN", "Only owners/admins/creators can delete.")
    await db.delete(project)
    await db.commit()
