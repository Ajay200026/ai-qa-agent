from pydantic import BaseModel, Field


class BusinessAction(BaseModel):
    action: str
    field: str | None = None
    value: str | None = None
    description: str | None = None


class ParsedScenario(BaseModel):
    template_key: str = "DATA_CHANGE_REQUEST"
    inputs: dict[str, str] = Field(default_factory=dict)
    business_actions: list[BusinessAction] = Field(default_factory=list)
    expected_results: list[str] = Field(default_factory=list)
    objective: str = ""
