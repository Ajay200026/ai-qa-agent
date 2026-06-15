from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowStepDef(BaseModel):
    seq: int
    action: str
    name: str
    params: dict = Field(default_factory=dict)
    optional: bool = False
    skip_if_input: str | None = None
    require_input: str | None = None


class WorkflowTemplateCreate(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    steps: list[WorkflowStepDef]
    input_schema: dict = Field(default_factory=dict)
    is_active: bool = True


class WorkflowTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    steps: list[WorkflowStepDef] | None = None
    input_schema: dict | None = None
    is_active: bool | None = None


class WorkflowTemplateSummary(BaseModel):
    key: str
    name: str
    description: str | None
    input_schema: dict

    model_config = {"from_attributes": True}


class WorkflowTemplateResponse(BaseModel):
    id: UUID
    key: str
    name: str
    description: str | None
    steps: list
    input_schema: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowPreviewRequest(BaseModel):
    inputs: dict[str, str] = Field(default_factory=dict)
    business_actions: list[dict] = Field(default_factory=list)
    expected_results: list[str] = Field(default_factory=list)


class WorkflowPreviewResponse(BaseModel):
    template_key: str
    planned_steps: list[dict]
    expected_results: list[str]
