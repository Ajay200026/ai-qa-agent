from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ExecutionCreate(BaseModel):
    scenario_id: UUID
    org_id: UUID


class ExecutionStepResponse(BaseModel):
    id: UUID
    seq: int
    name: str
    action: str
    status: str
    screenshot_path: str | None
    error: str | None
    action_params: dict | None = None
    notes: str | None = None
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class ExecutionRerunRequest(BaseModel):
    from_step_seq: int | None = None


class StepParamsUpdate(BaseModel):
    params: dict = Field(default_factory=dict)


class StepNotesUpdate(BaseModel):
    notes: str | None = None


class ExecutionResponse(BaseModel):
    id: UUID
    scenario_id: UUID
    org_id: UUID
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    plan_json: dict | None
    created_at: datetime
    steps: list[ExecutionStepResponse] = []

    model_config = {"from_attributes": True}


class ExecutionEvent(BaseModel):
    execution_id: UUID
    event_type: str
    step_seq: int | None = None
    step_name: str | None = None
    status: str | None = None
    message: str | None = None
    screenshot_path: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
