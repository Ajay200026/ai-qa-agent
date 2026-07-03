import json
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, UploadFile

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import AppException
from app.schemas.login_as import IdentityPreviewRequest, IdentityPreviewResponse
from app.schemas.scenario import ScenarioCreate, ScenarioResponse, ScenarioUpdate
from app.services.identity_preview import preview_identities_from_content
from app.services.scenario_service import ScenarioService

router = APIRouter()


@router.post("/preview-identities", response_model=IdentityPreviewResponse)
async def preview_identities(
    payload: IdentityPreviewRequest,
    current_user: CurrentUser,
):
    """Parse test pack content and return unique (bottler, role) pairs."""
    return preview_identities_from_content(payload.test_pack_content)


@router.post("", response_model=ScenarioResponse, status_code=201)
async def create_scenario(
    db: DbSession,
    current_user: CurrentUser,
    project_id: UUID = Form(...),
    name: str = Form(...),
    description: str = Form(...),
    acceptance_criteria: str = Form(...),
    template_key: str | None = Form(None),
    inputs: str | None = Form(None),
    business_actions: str | None = Form(None),
    expected_results: str | None = Form(None),
    test_pack_content: str | None = Form(None),
    customer_target: str | None = Form(None),
    login_as_target: str | None = Form(None),
    identity_map: str | None = Form(None),
    account_query_id: str | None = Form(None),
    login_as_profile_id: str | None = Form(None),
    test_case_file: UploadFile | None = None,
    regression_file: UploadFile | None = None,
):
    service = ScenarioService(db)
    data = ScenarioCreate(
        project_id=project_id,
        name=name,
        description=description,
        acceptance_criteria=acceptance_criteria,
        template_key=template_key,
        inputs=json.loads(inputs) if inputs else {},
        business_actions=json.loads(business_actions) if business_actions else [],
        expected_results=json.loads(expected_results) if expected_results else [],
        test_pack_content=test_pack_content,
        customer_target=json.loads(customer_target) if customer_target else None,
        login_as_target=json.loads(login_as_target) if login_as_target else None,
        identity_map=json.loads(identity_map) if identity_map else None,
        account_query_id=UUID(account_query_id) if account_query_id else None,
        login_as_profile_id=UUID(login_as_profile_id) if login_as_profile_id else None,
    )
    scenario = await service.create(data, test_case_file, regression_file)
    await db.commit()
    return scenario


@router.patch("/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    scenario_id: UUID,
    payload: ScenarioUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    service = ScenarioService(db)
    try:
        scenario = await service.update(scenario_id, payload)
        await db.commit()
        return scenario
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=list[ScenarioResponse])
async def list_scenarios(project_id: UUID, db: DbSession, current_user: CurrentUser):
    service = ScenarioService(db)
    return await service.list_by_project(project_id)


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(scenario_id: UUID, db: DbSession, current_user: CurrentUser):
    service = ScenarioService(db)
    try:
        return await service.get(scenario_id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
