from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ScenarioCreate(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=255)
    description: str
    acceptance_criteria: str
    template_key: str | None = None
    inputs: dict = Field(default_factory=dict)
    business_actions: list = Field(default_factory=list)
    expected_results: list = Field(default_factory=list)


class ScenarioResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str
    acceptance_criteria: str
    template_key: str | None
    inputs: dict
    business_actions: list
    expected_results: list
    test_case_file: str | None
    regression_file: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
