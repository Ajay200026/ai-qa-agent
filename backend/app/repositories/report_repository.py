from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report
from app.repositories.base import BaseRepository


class ReportRepository(BaseRepository[Report]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Report)

    async def get_by_execution(self, execution_id: UUID) -> Report | None:
        result = await self.db.execute(
            select(Report).where(Report.execution_id == execution_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 50, offset: int = 0) -> list[Report]:
        result = await self.db.execute(
            select(Report).order_by(Report.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
