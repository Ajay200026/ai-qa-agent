from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import WorkflowFieldRegistry, WorkflowTemplate


class WorkflowRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_active(self) -> list[WorkflowTemplate]:
        result = await self.db.execute(
            select(WorkflowTemplate)
            .where(WorkflowTemplate.is_active.is_(True))
            .order_by(WorkflowTemplate.name)
        )
        return list(result.scalars().all())

    async def get_by_key(self, key: str) -> WorkflowTemplate | None:
        result = await self.db.execute(
            select(WorkflowTemplate).where(WorkflowTemplate.key == key)
        )
        return result.scalar_one_or_none()

    async def create(self, template: WorkflowTemplate) -> WorkflowTemplate:
        self.db.add(template)
        await self.db.flush()
        await self.db.refresh(template)
        return template

    async def update(self, template: WorkflowTemplate) -> WorkflowTemplate:
        await self.db.flush()
        await self.db.refresh(template)
        return template

    async def get_field_registry(
        self, template_key: str, field_name: str
    ) -> WorkflowFieldRegistry | None:
        result = await self.db.execute(
            select(WorkflowFieldRegistry).where(
                WorkflowFieldRegistry.template_key == template_key,
                WorkflowFieldRegistry.field_name == field_name,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_field_registry(
        self,
        template_key: str,
        field_name: str,
        field_type: str,
        locator_hints: list,
    ) -> WorkflowFieldRegistry:
        existing = await self.get_field_registry(template_key, field_name)
        if existing:
            existing.field_type = field_type
            existing.locator_hints = locator_hints
            from datetime import UTC, datetime

            existing.last_verified_at = datetime.now(UTC)
            await self.db.flush()
            return existing
        entry = WorkflowFieldRegistry(
            template_key=template_key,
            field_name=field_name,
            field_type=field_type,
            locator_hints=locator_hints,
        )
        from datetime import UTC, datetime

        entry.last_verified_at = datetime.now(UTC)
        self.db.add(entry)
        await self.db.flush()
        return entry
