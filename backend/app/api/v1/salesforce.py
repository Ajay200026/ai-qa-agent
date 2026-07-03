from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import AppException
from app.knowledge.customer_search_rules import (
    default_soql_for_bottler,
    valid_combinations,
)
from app.schemas.customer_target import SoqlQueryRequest, SoqlQueryResponse
from app.schemas.salesforce import (
    SalesforceOAuthCallbackRequest,
    SalesforceOAuthCallbackResponse,
    SalesforceOAuthStartRequest,
    SalesforceOAuthStartResponse,
    SalesforceOrgCreate,
    SalesforceOrgResponse,
    SalesforceOrgUpdate,
    SalesforceValidateResponse,
)
from app.services.salesforce_oauth import (
    consume_authorize_redirect_session,
    exchange_oauth_code,
    start_oauth_flow,
)
from app.services.salesforce_query import (
    SoqlAuthError,
    SoqlClient,
    SoqlExecutionError,
    SoqlValidationError,
)
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


@router.patch("/orgs/{org_id}", response_model=SalesforceOrgResponse)
async def update_org(
    org_id: UUID,
    data: SalesforceOrgUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    service = SalesforceService(db)
    try:
        return await service.update_org(org_id, data)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/orgs/{org_id}", status_code=204)
async def delete_org(org_id: UUID, db: DbSession, current_user: CurrentUser):
    service = SalesforceService(db)
    try:
        await service.delete_org(org_id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/orgs/{org_id}/validate", response_model=SalesforceValidateResponse)
async def validate_org(org_id: UUID, db: DbSession, current_user: CurrentUser):
    service = SalesforceService(db)
    valid, message = await service.validate_org(org_id)
    return SalesforceValidateResponse(org_id=org_id, valid=valid, message=message)


@router.get("/orgs/oauth/redirect/{session_id}")
async def oauth_redirect_to_salesforce(session_id: str):
    """Browser navigation endpoint — 302 redirect to Salesforce login (no JS required)."""
    try:
        authorization_url = consume_authorize_redirect_session(session_id)
        return RedirectResponse(url=authorization_url, status_code=302)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/orgs/oauth/start", response_model=SalesforceOAuthStartResponse)
async def oauth_start(
    payload: SalesforceOAuthStartRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    try:
        authorization_url, state, redirect_session = await start_oauth_flow(
            project_id=payload.project_id,
            name=payload.name,
            org_type=payload.org_type,
            login_url=payload.login_url,
            role=payload.role,
            bottler=payload.bottler,
            is_default=payload.is_default,
        )
        return SalesforceOAuthStartResponse(
            authorization_url=authorization_url,
            state=state,
            redirect_session=redirect_session,
        )
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/orgs/oauth/callback", response_model=SalesforceOAuthCallbackResponse)
async def oauth_callback(
    payload: SalesforceOAuthCallbackRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    service = SalesforceService(db)
    try:
        token_data = await exchange_oauth_code(state=payload.state, code=payload.code)
        org = await service.create_oauth_org(
            project_id=token_data["project_id"],
            name=token_data["name"],
            org_type=token_data["org_type"],
            login_url=token_data["login_url"],
            instance_url=token_data["instance_url"],
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            username=token_data.get("username"),
            role=token_data.get("role"),
            bottler=token_data.get("bottler"),
            is_default=token_data.get("is_default", False),
        )
        await db.commit()
        return SalesforceOAuthCallbackResponse(org=SalesforceOrgResponse.model_validate(org))
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/orgs/{org_id}/query", response_model=SoqlQueryResponse)
async def query_org(
    org_id: UUID,
    payload: SoqlQueryRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Execute a vetted read-only SOQL query against Account or User."""
    from app.services.salesforce_query import validate_soql

    try:
        cleaned, object_name = validate_soql(payload.soql, limit=payload.limit)
    except SoqlValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    service = SalesforceService(db)
    try:
        org = await service.get_org(org_id)
        credentials = service.get_decrypted_credentials(org)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    client = SoqlClient(org=org, credentials=credentials)
    try:
        if object_name == "User":
            rows = await client.query_users(cleaned, limit=payload.limit)
            return SoqlQueryResponse(
                total_size=len(rows),
                users=[r.model_dump() for r in rows],
                done=True,
            )
        return await client.query(cleaned, limit=payload.limit)
    except SoqlValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SoqlAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except SoqlExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/orgs/{org_id}/customer-search-options")
async def customer_search_options(
    org_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    sales_office: str | None = None,
):
    """Return valid Account Group + Distribution Channel combinations for the org's bottler."""
    service = SalesforceService(db)
    try:
        org = await service.get_org(org_id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return {
        "bottler": org.bottler,
        "sales_office": sales_office,
        "combinations": valid_combinations(org.bottler, sales_office),
        "default_soql": default_soql_for_bottler(org.bottler),
    }
