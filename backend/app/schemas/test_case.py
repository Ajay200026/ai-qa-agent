from enum import StrEnum

from pydantic import BaseModel, Field


class AssertionKind(StrEnum):
    TOAST_CONTAINS = "toast_contains"
    TOAST_EQUALS = "toast_equals"
    FIELD_EDITABLE = "field_editable"
    FIELD_READONLY = "field_readonly"
    FIELD_VALUE_EQUALS = "field_value_equals"
    FIELD_PRESENT = "field_present"
    NO_TOAST = "no_toast"
    TEXT_VISIBLE = "text_visible"
    TEXT_NOT_VISIBLE = "text_not_visible"
    REQUEST_CREATED = "request_created"
    STATUS_SUBMITTED = "status_submitted"


class Assertion(BaseModel):
    kind: AssertionKind
    target: str | None = None
    expected: str | None = None
    comparator: str | None = None


class TestStep(BaseModel):
    seq: int
    action: str
    target: str | None = None
    value: str | None = None
    description: str = ""
    assertions: list[Assertion] = Field(default_factory=list)
    params: dict = Field(default_factory=dict)


class TestCase(BaseModel):
    tc_id: str
    title: str
    role: str | None = None
    bottler: str | None = None
    preconditions: list[str] = Field(default_factory=list)
    steps: list[TestStep] = Field(default_factory=list)
    expected_summary: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class TestPack(BaseModel):
    title: str = ""
    module: str | None = None
    bottler: str | None = None
    shared_preconditions: list[str] = Field(default_factory=list)
    test_cases: list[TestCase] = Field(default_factory=list)
    smoke_subset: list[str] = Field(default_factory=list)


class AssertionEvidence(BaseModel):
    kind: str
    passed: bool
    expected: str | None = None
    actual: str | None = None
    detail: str = ""
    screenshot_path: str | None = None


class TestStepResult(BaseModel):
    seq: int
    action: str
    description: str = ""
    status: str  # passed | failed | blocked | skipped
    error: str | None = None
    screenshot_path: str | None = None
    assertion_results: list[AssertionEvidence] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    duration_ms: int | None = None
    retry_count: int = 0


class TestCaseResult(BaseModel):
    tc_id: str
    title: str
    status: str  # passed | failed | blocked | skipped
    role: str | None = None
    bottler: str | None = None
    step_results: list[TestStepResult] = Field(default_factory=list)
    error: str | None = None
    is_smoke: bool = False


class TestPackResult(BaseModel):
    title: str = ""
    passed_count: int = 0
    failed_count: int = 0
    blocked_count: int = 0
    skipped_count: int = 0
    test_case_results: list[TestCaseResult] = Field(default_factory=list)
    smoke_subset: list[str] = Field(default_factory=list)
