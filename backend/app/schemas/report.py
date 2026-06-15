from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ReportResponse(BaseModel):
    id: UUID
    execution_id: UUID
    summary: str
    passed_count: int
    failed_count: int
    llm_analysis: str | None
    artifacts_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    total_executions: int
    success_rate: float
    failed_executions: int
    connected_orgs: int
