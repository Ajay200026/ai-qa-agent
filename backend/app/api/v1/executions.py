from uuid import UUID

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import inspect

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import AppException
from app.events.manager import event_manager
from app.schemas.execution import (
    ExecutionCreate,
    ExecutionRerunRequest,
    ExecutionResponse,
    ExecutionStepResponse,
    StepNotesUpdate,
    StepParamsUpdate,
)
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
    payload: ExecutionRerunRequest | None = None,
):
    service = ExecutionService(db)
    try:
        execution = await service.rerun_execution(
            execution_id,
            from_step_seq=payload.from_step_seq if payload else None,
        )
        await db.commit()
        schedule_execution_run(execution.id)
        return _to_response(execution)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.patch("/{execution_id}/steps/{seq}", response_model=ExecutionStepResponse)
async def patch_execution_step(
    execution_id: UUID,
    seq: int,
    payload: StepParamsUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    service = ExecutionService(db)
    try:
        step = await service.update_step_params(execution_id, seq, payload.params)
        await db.commit()
        return ExecutionStepResponse.model_validate(step)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.put("/{execution_id}/steps/{seq}/notes", response_model=ExecutionStepResponse)
async def put_execution_step_notes(
    execution_id: UUID,
    seq: int,
    payload: StepNotesUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    service = ExecutionService(db)
    try:
        step = await service.update_step_notes(execution_id, seq, payload.notes)
        await db.commit()
        return ExecutionStepResponse.model_validate(step)
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


@router.delete("/failed", status_code=200)
async def clear_failed_executions(db: DbSession, current_user: CurrentUser):
    service = ExecutionService(db)
    deleted = await service.clear_failed_executions()
    await db.commit()
    return {"deleted": deleted}


@router.delete("/history", status_code=200)
async def clear_execution_history(db: DbSession, current_user: CurrentUser):
    service = ExecutionService(db)
    deleted = await service.clear_execution_history()
    await db.commit()
    return {"deleted": deleted}


@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(execution_id: UUID, db: DbSession, current_user: CurrentUser):
    service = ExecutionService(db)
    try:
        execution = await service.get_execution(execution_id)
        return _to_response(execution)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/{execution_id}", status_code=204)
async def delete_execution(execution_id: UUID, db: DbSession, current_user: CurrentUser):
    service = ExecutionService(db)
    try:
        await service.delete_execution(execution_id)
        await db.commit()
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
