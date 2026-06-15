from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.execution import Execution, ExecutionStep, ExecutionStatus
from app.models.report import Report
from app.repositories.base import BaseRepository


class ExecutionRepository(BaseRepository[Execution]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Execution)

    async def get_with_steps(self, execution_id: UUID) -> Execution | None:
        result = await self.db.execute(
            select(Execution)
            .options(selectinload(Execution.steps))
            .where(Execution.id == execution_id)
        )
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 20) -> list[Execution]:
        result = await self.db.execute(
            select(Execution).order_by(Execution.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def list_failed(self, limit: int = 10) -> list[Execution]:
        result = await self.db.execute(
            select(Execution)
            .where(Execution.status == ExecutionStatus.FAILED)
            .order_by(Execution.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_stats(self) -> dict:
        total_result = await self.db.execute(select(func.count(Execution.id)))
        total = total_result.scalar() or 0

        passed_result = await self.db.execute(
            select(func.count(Execution.id)).where(Execution.status == ExecutionStatus.PASSED)
        )
        passed = passed_result.scalar() or 0

        failed_result = await self.db.execute(
            select(func.count(Execution.id)).where(Execution.status == ExecutionStatus.FAILED)
        )
        failed = failed_result.scalar() or 0

        success_rate = (passed / total * 100) if total > 0 else 0.0
        return {"total": total, "passed": passed, "failed": failed, "success_rate": success_rate}

    async def update_status(
        self,
        execution: Execution,
        status: str,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        duration_ms: int | None = None,
        plan_json: dict | None = None,
    ) -> Execution:
        execution.status = status
        if started_at:
            execution.started_at = started_at
        if finished_at:
            execution.finished_at = finished_at
        if duration_ms is not None:
            execution.duration_ms = duration_ms
        if plan_json is not None:
            execution.plan_json = plan_json
        await self.db.flush()
        await self.db.refresh(execution)
        return execution

    async def create_step(self, step: ExecutionStep) -> ExecutionStep:
        self.db.add(step)
        await self.db.flush()
        await self.db.refresh(step)
        return step

    async def reset_for_rerun(self, execution: Execution) -> Execution:
        await self.db.execute(delete(ExecutionStep).where(ExecutionStep.execution_id == execution.id))
        await self.db.execute(delete(Report).where(Report.execution_id == execution.id))
        execution.status = ExecutionStatus.QUEUED
        execution.started_at = None
        execution.finished_at = None
        execution.duration_ms = None
        execution.plan_json = None
        await self.db.flush()
        await self.db.refresh(execution)
        return execution

    async def update_step(
        self,
        step: ExecutionStep,
        *,
        status: str | None = None,
        screenshot_path: str | None = None,
        error: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> ExecutionStep:
        if status:
            step.status = status
        if screenshot_path is not None:
            step.screenshot_path = screenshot_path
        if error is not None:
            step.error = error
        if started_at:
            step.started_at = started_at
        if finished_at:
            step.finished_at = finished_at
        await self.db.flush()
        await self.db.refresh(step)
        return step
