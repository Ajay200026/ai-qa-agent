from uuid import UUID

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import inspect

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import AppException
from app.events.manager import event_manager
from app.schemas.execution import ExecutionCreate, ExecutionResponse, ExecutionStepResponse
from app.services.execution_service import ExecutionService, schedule_execution_run

router = APIRouter()


def _to_response(execution) -> ExecutionResponse:
    state = inspect(execution)
    if "steps" in state.unloaded:
        step_models = []
    else:
        step_models = list(execution.steps or [])
    steps = [ExecutionStepResponse.model_validate(s) for s in step_models]
    return ExecutionResponse(
        id=execution.id,
        scenario_id=execution.scenario_id,
        org_id=execution.org_id,
        status=execution.status,
        started_at=execution.started_at,
        finished_at=execution.finished_at,
        duration_ms=execution.duration_ms,
        plan_json=execution.plan_json,
        created_at=execution.created_at,
        steps=steps,
    )


@router.post("", response_model=ExecutionResponse, status_code=201)
async def create_execution(
    data: ExecutionCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    service = ExecutionService(db)
    try:
        execution = await service.create_execution(data)
        await db.commit()
        schedule_execution_run(execution.id)
        return _to_response(execution)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/{execution_id}/stop", response_model=ExecutionResponse)
async def stop_execution(
    execution_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
):
    service = ExecutionService(db)
    try:
        execution = await service.stop_execution(execution_id)
        await db.commit()
        return _to_response(execution)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/{execution_id}/rerun", response_model=ExecutionResponse)
async def rerun_execution(
    execution_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
):
    service = ExecutionService(db)
    try:
        execution = await service.rerun_execution(execution_id)
        await db.commit()
        schedule_execution_run(execution.id)
        return _to_response(execution)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=list[ExecutionResponse])
async def list_executions(db: DbSession, current_user: CurrentUser, limit: int = 20):
    service = ExecutionService(db)
    executions = await service.list_recent(limit)
    return [_to_response(e) for e in executions]


@router.get("/failed", response_model=list[ExecutionResponse])
async def list_failed_executions(db: DbSession, current_user: CurrentUser, limit: int = 10):
    service = ExecutionService(db)
    executions = await service.list_failed(limit)
    results = []
    for e in executions:
        full = await service.get_execution(e.id)
        results.append(_to_response(full))
    return results


@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(execution_id: UUID, db: DbSession, current_user: CurrentUser):
    service = ExecutionService(db)
    try:
        execution = await service.get_execution(execution_id)
        return _to_response(execution)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.websocket("/{execution_id}/stream")
async def execution_stream(execution_id: UUID, websocket: WebSocket):
    await event_manager.connect(execution_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await event_manager.disconnect(execution_id, websocket)
