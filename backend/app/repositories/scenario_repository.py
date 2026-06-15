from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scenario import Scenario
from app.repositories.base import BaseRepository


class ScenarioRepository(BaseRepository[Scenario]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Scenario)

    async def list_by_project(self, project_id: UUID) -> list[Scenario]:
        result = await self.db.execute(
            select(Scenario)
            .where(Scenario.project_id == project_id)
            .order_by(Scenario.created_at.desc())
        )
        return list(result.scalars().all())
