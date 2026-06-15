from pydantic import BaseModel, Field


class ExecutionPlanStep(BaseModel):
    action: str
    description: str
    target: str | None = None
    value: str | None = None
    expected: str | None = None


class ExecutionPlan(BaseModel):
    scenario_name: str
    objective: str
    steps: list[ExecutionPlanStep]
    acceptance_checks: list[str] = Field(default_factory=list)


class PlannedStep(BaseModel):
    seq: int
    name: str
    action: str
    params: dict = Field(default_factory=dict)


class StepResult(BaseModel):
    seq: int
    name: str
    action: str
    status: str
    screenshot_path: str | None = None
    error: str | None = None
    logs: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    passed: bool
    checks: list[dict]
    llm_verdict: str | None = None


class ExecutionReport(BaseModel):
    passed: bool
    summary: str
    passed_count: int
    failed_count: int
    llm_analysis: str | None = None
    step_results: list[StepResult] = Field(default_factory=list)
