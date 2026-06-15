import json
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, UploadFile

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import AppException
from app.schemas.scenario import ScenarioCreate, ScenarioResponse
from app.services.scenario_service import ScenarioService

router = APIRouter()


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
    )
    scenario = await service.create(data, test_case_file, regression_file)
    await db.commit()
    return scenario


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
