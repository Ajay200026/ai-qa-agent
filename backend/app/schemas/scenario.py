from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.customer_target import CustomerTarget
from app.schemas.login_as import IdentityMap, LoginAsTarget


class ScenarioCreate(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=255)
    description: str
    acceptance_criteria: str
    template_key: str | None = None
    inputs: dict = Field(default_factory=dict)
    business_actions: list = Field(default_factory=list)
    expected_results: list = Field(default_factory=list)
    test_pack_content: str | None = None
    customer_target: CustomerTarget | None = None
    login_as_target: LoginAsTarget | None = None
    identity_map: IdentityMap | None = None
    account_query_id: UUID | None = None
    login_as_profile_id: UUID | None = None


class ScenarioUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    acceptance_criteria: str | None = None
    template_key: str | None = None
    inputs: dict | None = None
    business_actions: list | None = None
    expected_results: list | None = None
    test_pack_content: str | None = None
    customer_target: CustomerTarget | None = None
    login_as_target: LoginAsTarget | None = None
    identity_map: IdentityMap | None = None
    account_query_id: UUID | None = None
    login_as_profile_id: UUID | None = None


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
    test_pack_content: str | None = None
    customer_target: CustomerTarget | None = None
    login_as_target: LoginAsTarget | None = None
    identity_map: IdentityMap | None = None
    account_query_id: UUID | None = None
    login_as_profile_id: UUID | None = None
    test_case_file: str | None
    regression_file: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
