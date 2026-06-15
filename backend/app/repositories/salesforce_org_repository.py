from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.salesforce_org import SalesforceOrg
from app.repositories.base import BaseRepository


class SalesforceOrgRepository(BaseRepository[SalesforceOrg]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, SalesforceOrg)

    async def list_by_project(self, project_id: UUID) -> list[SalesforceOrg]:
        result = await self.db.execute(
            select(SalesforceOrg)
            .where(SalesforceOrg.project_id == project_id)
            .order_by(SalesforceOrg.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_connected(self) -> list[SalesforceOrg]:
        result = await self.db.execute(
            select(SalesforceOrg).where(SalesforceOrg.status == "connected")
        )
        return list(result.scalars().all())
