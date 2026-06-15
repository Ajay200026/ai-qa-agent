from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.report import Report
from app.repositories.report_repository import ReportRepository
from app.repositories.salesforce_org_repository import SalesforceOrgRepository
from app.repositories.execution_repository import ExecutionRepository
from app.schemas.report import DashboardStats


class ReportService:
    def __init__(self, db: AsyncSession):
        self.repo = ReportRepository(db)
        self.execution_repo = ExecutionRepository(db)
        self.org_repo = SalesforceOrgRepository(db)

    async def get(self, report_id: UUID) -> Report:
        report = await self.repo.get_by_id(report_id)
        if not report:
            raise NotFoundError("Report", report_id)
        return report

    async def get_by_execution(self, execution_id: UUID) -> Report:
        report = await self.repo.get_by_execution(execution_id)
        if not report:
            raise NotFoundError("Report", f"execution:{execution_id}")
        return report

    async def list_all(self, limit: int = 50) -> list[Report]:
        return await self.repo.list_all(limit=limit)

    async def get_dashboard_stats(self) -> DashboardStats:
        stats = await self.execution_repo.get_stats()
        connected = await self.org_repo.list_connected()
        return DashboardStats(
            total_executions=stats["total"],
            success_rate=round(stats["success_rate"], 2),
            failed_executions=stats["failed"],
            connected_orgs=len(connected),
        )
