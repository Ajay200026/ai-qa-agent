from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import AppException
from app.schemas.artifact import ArtifactListResponse
from app.schemas.report import DashboardStats, ReportResponse
from app.services.artifact_service import list_artifact_files, resolve_artifact_path
from app.services.report_export_service import ReportExportService
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


@router.get("/artifacts/{execution_id}", response_model=ArtifactListResponse)
async def list_artifacts(execution_id: UUID, current_user: CurrentUser):
    return ArtifactListResponse(files=list_artifact_files(execution_id))


@router.get("/artifacts/{execution_id}/{filename}")
async def get_artifact(execution_id: UUID, filename: str, current_user: CurrentUser):
    try:
        filepath = resolve_artifact_path(execution_id, filename)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return FileResponse(filepath)


@router.get("/execution/{execution_id}", response_model=ReportResponse)
async def get_report_by_execution(execution_id: UUID, db: DbSession, current_user: CurrentUser):
    service = ReportService(db)
    try:
        return await service.get_by_execution(execution_id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/{report_id}/download")
async def download_report(
    report_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    format: str = Query("zip", pattern="^(zip|pdf)$"),
):
    service = ReportExportService(db)
    try:
        if format == "pdf":
            content, filename = await service.build_pdf(report_id)
            media_type = "application/pdf"
        else:
            content, filename = await service.build_zip(report_id)
            media_type = "application/zip"
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: UUID, db: DbSession, current_user: CurrentUser):
    service = ReportService(db)
    try:
        return await service.get(report_id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
