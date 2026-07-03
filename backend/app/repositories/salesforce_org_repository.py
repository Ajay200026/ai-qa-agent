from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import Execution
from app.models.salesforce_org import SalesforceOrg
from app.repositories.base import BaseRepository


class SalesforceOrgRepository(BaseRepository[SalesforceOrg]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, SalesforceOrg)

    async def list_by_project(self, project_id: UUID) -> list[SalesforceOrg]:
        result = await self.db.execute(
            select(SalesforceOrg)
            .where(SalesforceOrg.project_id == project_id)
            .order_by(SalesforceOrg.is_default.desc(), SalesforceOrg.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_connected(self) -> list[SalesforceOrg]:
        result = await self.db.execute(
            select(SalesforceOrg).where(SalesforceOrg.status == "connected")
        )
        return list(result.scalars().all())

    async def count_executions(self, org_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Execution).where(Execution.org_id == org_id)
        )
        return int(result.scalar_one())

    async def clear_default_for_project(self, project_id: UUID, *, except_org_id: UUID | None = None) -> None:
        stmt = (
            update(SalesforceOrg)
            .where(SalesforceOrg.project_id == project_id)
            .values(is_default=False)
        )
        if except_org_id is not None:
            stmt = stmt.where(SalesforceOrg.id != except_org_id)
        await self.db.execute(stmt)
