"""RCA analysis output schema."""

from pydantic import BaseModel, Field


class RCAAnalysis(BaseModel):
    what_failed: str = ""
    why_failed: str = ""
    where_failed: str = ""
    business_impact: str = ""
    suggested_fix: str = Field("", description="Recommendation only — no code changes")
    graph_path: list[str] = Field(default_factory=list)
