from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.repositories.workflow_repository import WorkflowRepository
from app.workflows.base import DatabaseWorkflowStrategy, WorkflowStrategy


class WorkflowFactory:
    @staticmethod
    async def create(template_key: str, db: AsyncSession) -> WorkflowStrategy:
        repo = WorkflowRepository(db)
        template = await repo.get_by_key(template_key)
        if not template:
            active = await repo.list_active()
            available = ", ".join(t.key for t in active) or "none"
            raise NotFoundError(
                "WorkflowTemplate",
                f"{template_key} (available: {available})",
            )
        return DatabaseWorkflowStrategy(
            template_key=template.key,
            template_name=template.name,
            steps=template.steps,
            input_schema=template.input_schema,
        )

    @staticmethod
    async def list_keys(db: AsyncSession) -> list[str]:
        repo = WorkflowRepository(db)
        templates = await repo.list_active()
        return [t.key for t in templates]
