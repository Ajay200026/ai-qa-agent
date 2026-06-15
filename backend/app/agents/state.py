from typing import Annotated, Any, TypedDict
from uuid import UUID

from langgraph.graph.message import add_messages

from app.schemas.agent import (
    ExecutionPlan,
    ExecutionReport,
    PlannedStep,
    StepResult,
    ValidationResult,
)
from app.schemas.parsed_scenario import ParsedScenario


class ExecutionState(TypedDict, total=False):
    execution_id: UUID
    scenario_name: str
    scenario_description: str
    acceptance_criteria: str
    test_case_content: str
    regression_content: str
    template_key: str | None
    inputs: dict[str, str]
    business_actions: list[dict]
    expected_results: list[str]
    parsed_scenario: ParsedScenario
    org_credentials: dict[str, Any]
    login_url: str
    auth_method: str
    instance_url: str | None
    artifacts_dir: str
    plan: ExecutionPlan
    planned_steps: list[PlannedStep]
    current_step_index: int
    retry_count: int
    max_retries: int
    step_results: list[StepResult]
    validation: ValidationResult
    report: ExecutionReport
    logs: Annotated[list[str], add_messages]
    error: str | None
