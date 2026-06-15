from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import AppException
from app.schemas.salesforce import SalesforceOrgCreate, SalesforceOrgResponse, SalesforceValidateResponse
from app.services.salesforce_service import SalesforceService

router = APIRouter()


@router.post("/orgs", response_model=SalesforceOrgResponse, status_code=201)
async def create_org(data: SalesforceOrgCreate, db: DbSession, current_user: CurrentUser):
    service = SalesforceService(db)
    try:
        return await service.create_org(data)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/orgs", response_model=list[SalesforceOrgResponse])
async def list_orgs(project_id: UUID, db: DbSession, current_user: CurrentUser):
    service = SalesforceService(db)
    return await service.list_by_project(project_id)


@router.get("/orgs/{org_id}", response_model=SalesforceOrgResponse)
async def get_org(org_id: UUID, db: DbSession, current_user: CurrentUser):
    service = SalesforceService(db)
    try:
        return await service.get_org(org_id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/orgs/{org_id}/validate", response_model=SalesforceValidateResponse)
async def validate_org(org_id: UUID, db: DbSession, current_user: CurrentUser):
    service = SalesforceService(db)
    valid, message = await service.validate_org(org_id)
    return SalesforceValidateResponse(org_id=org_id, valid=valid, message=message)
