"""Projects — the folders a person keeps their designs in.

A project is a name and an owner. Filing a design under one changes nothing
about the design: not its requirement, its version, its claims or its files.
The filing itself is PUT /design/{id}/project (api/routes/design.py).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.auth import get_current_user
from db.crud import create_project, get_project, list_user_projects, rename_project
from db.models import get_db
from middleware.rate_limit import limiter

router = APIRouter()

MAX_NAME = 80


class ProjectName(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _named(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("a project needs a name")
        if len(value) > MAX_NAME:
            raise ValueError(f"a project name is at most {MAX_NAME} characters")
        return value


def project_view(project) -> dict:
    created = getattr(project, "created_at", None)
    return {
        "id": str(project.id),
        "name": project.name,
        "created_at": created.isoformat() if created else None,
    }


async def load_owned_project(db: AsyncSession, project_id: str, user):
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(404, detail="Project not found")
    if str(project.user_id) != str(user.id):
        raise HTTPException(403, detail="Access denied")
    return project


@router.get("")
async def list_projects(
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    return [project_view(p) for p in await list_user_projects(db, str(user.id))]


@router.post("", status_code=201)
@limiter.limit("60/hour")
async def new_project(
    request: Request,
    body: ProjectName,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    return project_view(await create_project(db, str(user.id), body.name))


@router.put("/{project_id}")
@limiter.limit("120/hour")
async def name_project(
    request: Request,
    project_id: str,
    body: ProjectName,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    project = await load_owned_project(db, project_id, user)
    await rename_project(db, project_id, body.name)
    return {**project_view(project), "name": body.name}
