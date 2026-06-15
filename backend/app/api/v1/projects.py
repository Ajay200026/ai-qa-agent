from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import AppException
from app.schemas.project import ProjectCreate, ProjectResponse
from app.services.project_service import ProjectService

router = APIRouter()


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(data: ProjectCreate, db: DbSession, current_user: CurrentUser):
    service = ProjectService(db)
    return await service.create(data, current_user)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(db: DbSession, current_user: CurrentUser):
    service = ProjectService(db)
    return await service.list_for_user(current_user)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: UUID, db: DbSession, current_user: CurrentUser):
    service = ProjectService(db)
    try:
        return await service.get(project_id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
