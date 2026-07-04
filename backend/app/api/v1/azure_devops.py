"""Azure DevOps connection and repository picker API."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.azure_devops import (
    AzureBranchListResponse,
    AzureConnectRequest,
    AzureConnectionResponse,
    AzureProjectItem,
    AzureRepoItem,
)
from app.services.azure_devops_connection_service import AzureDevOpsConnectionService

router = APIRouter()


@router.post("/connect", response_model=AzureConnectionResponse)
async def connect_azure(body: AzureConnectRequest, current_user: CurrentUser, db: DbSession):
    service = AzureDevOpsConnectionService(db)
    try:
        conn = await service.connect(
            current_user.id, body.name, body.organization_url, body.pat
        )
        return conn
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/connections", response_model=list[AzureConnectionResponse])
async def list_connections(current_user: CurrentUser, db: DbSession):
    service = AzureDevOpsConnectionService(db)
    return await service.list_connections(current_user.id)


@router.delete("/connections/{connection_id}", status_code=204)
async def delete_connection(connection_id: UUID, current_user: CurrentUser, db: DbSession):
    service = AzureDevOpsConnectionService(db)
    try:
        await service.delete_connection(connection_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/connections/{connection_id}/validate", response_model=AzureConnectionResponse)
async def validate_connection(connection_id: UUID, current_user: CurrentUser, db: DbSession):
    service = AzureDevOpsConnectionService(db)
    try:
        return await service.validate_connection(connection_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/connections/{connection_id}/projects", response_model=list[AzureProjectItem])
async def list_projects(connection_id: UUID, current_user: CurrentUser, db: DbSession):
    service = AzureDevOpsConnectionService(db)
    conn = await service.get_connection(connection_id, current_user.id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    try:
        client = service.client_for(conn)
        projects = await client.list_projects()
        return [AzureProjectItem(**p) for p in projects]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/connections/{connection_id}/projects/{project}/repos",
    response_model=list[AzureRepoItem],
)
async def list_repos(
    connection_id: UUID, project: str, current_user: CurrentUser, db: DbSession
):
    service = AzureDevOpsConnectionService(db)
    conn = await service.get_connection(connection_id, current_user.id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    try:
        client = service.client_for(conn)
        repos = await client.list_repositories(project)
        return [AzureRepoItem(**r) for r in repos]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/connections/{connection_id}/repos/{repo_id}/branches",
    response_model=AzureBranchListResponse,
)
async def list_branches(
    connection_id: UUID,
    repo_id: str,
    current_user: CurrentUser,
    db: DbSession,
    project: str = Query(..., min_length=1),
):
    service = AzureDevOpsConnectionService(db)
    conn = await service.get_connection(connection_id, current_user.id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    try:
        client = service.client_for(conn)
        branches = await client.list_branches(project, repo_id)
        return AzureBranchListResponse(branches=branches)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
