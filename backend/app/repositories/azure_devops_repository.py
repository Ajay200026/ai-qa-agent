"""Azure DevOps connection persistence."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.azure_devops import AzureDevOpsConnection
from app.repositories.base import BaseRepository


class AzureDevOpsConnectionRepository(BaseRepository[AzureDevOpsConnection]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, AzureDevOpsConnection)

    async def list_by_owner(self, owner_id: UUID) -> list[AzureDevOpsConnection]:
        result = await self.db.execute(
            select(AzureDevOpsConnection)
            .where(AzureDevOpsConnection.owner_id == owner_id)
            .order_by(AzureDevOpsConnection.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_owned(self, connection_id: UUID, owner_id: UUID) -> AzureDevOpsConnection | None:
        result = await self.db.execute(
            select(AzureDevOpsConnection).where(
                AzureDevOpsConnection.id == connection_id,
                AzureDevOpsConnection.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()
