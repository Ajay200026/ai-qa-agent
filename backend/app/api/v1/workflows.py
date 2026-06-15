from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import AppException
from app.schemas.workflow import (
    WorkflowPreviewRequest,
    WorkflowPreviewResponse,
    WorkflowTemplateCreate,
    WorkflowTemplateResponse,
    WorkflowTemplateSummary,
    WorkflowTemplateUpdate,
)
from app.services.workflow_service import WorkflowService

router = APIRouter()


@router.get("", response_model=list[WorkflowTemplateSummary])
async def list_workflows(db: DbSession, current_user: CurrentUser):
    service = WorkflowService(db)
    templates = await service.list_templates()
    return templates


@router.get("/{key}", response_model=WorkflowTemplateResponse)
async def get_workflow(key: str, db: DbSession, current_user: CurrentUser):
    service = WorkflowService(db)
    try:
        return await service.get_template(key)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("", response_model=WorkflowTemplateResponse, status_code=201)
async def create_workflow(
    data: WorkflowTemplateCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    service = WorkflowService(db)
    try:
        template = await service.create_template(data)
        await db.commit()
        return template
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{key}", response_model=WorkflowTemplateResponse)
async def update_workflow(
    key: str,
    data: WorkflowTemplateUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    service = WorkflowService(db)
    try:
        template = await service.update_template(key, data)
        await db.commit()
        return template
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/{key}/preview", response_model=WorkflowPreviewResponse)
async def preview_workflow(
    key: str,
    body: WorkflowPreviewRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    service = WorkflowService(db)
    try:
        planned, expected = await service.preview(key, body)
        return WorkflowPreviewResponse(
            template_key=key,
            planned_steps=[s.model_dump() for s in planned],
            expected_results=expected,
        )
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
