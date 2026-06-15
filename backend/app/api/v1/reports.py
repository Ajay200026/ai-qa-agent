from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import AppException
from app.schemas.report import DashboardStats, ReportResponse
from app.services.report_service import ReportService

router = APIRouter()


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard_stats(db: DbSession, current_user: CurrentUser):
    service = ReportService(db)
    return await service.get_dashboard_stats()


@router.get("", response_model=list[ReportResponse])
async def list_reports(db: DbSession, current_user: CurrentUser, limit: int = 50):
    service = ReportService(db)
    return await service.list_all(limit)


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: UUID, db: DbSession, current_user: CurrentUser):
    service = ReportService(db)
    try:
        return await service.get(report_id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/execution/{execution_id}", response_model=ReportResponse)
async def get_report_by_execution(execution_id: UUID, db: DbSession, current_user: CurrentUser):
    service = ReportService(db)
    try:
        return await service.get_by_execution(execution_id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/artifacts/{execution_id}/{filename}")
async def get_artifact(execution_id: UUID, filename: str, current_user: CurrentUser):
    from app.core.config import get_settings
    settings = get_settings()
    filepath = settings.artifacts_dir / str(execution_id) / filename
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(filepath)
