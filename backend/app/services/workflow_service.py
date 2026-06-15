import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.workflow import WorkflowTemplate
from app.repositories.workflow_repository import WorkflowRepository
from app.schemas.agent import ExecutionPlan, PlannedStep
from app.schemas.parsed_scenario import ParsedScenario
from app.schemas.workflow import WorkflowPreviewRequest, WorkflowTemplateCreate, WorkflowTemplateUpdate
from app.workflows.factory import WorkflowFactory
from app.workflows.template_matcher import TemplateMatcher

logger = logging.getLogger(__name__)


class WorkflowService:
    def __init__(self, db: AsyncSession):
        self.repo = WorkflowRepository(db)
        self.db = db

    async def list_templates(self) -> list[WorkflowTemplate]:
        return await self.repo.list_active()

    async def get_template(self, key: str) -> WorkflowTemplate:
        template = await self.repo.get_by_key(key)
        if not template:
            raise NotFoundError("WorkflowTemplate", key)
        return template

    async def create_template(self, data: WorkflowTemplateCreate) -> WorkflowTemplate:
        existing = await self.repo.get_by_key(data.key)
        if existing:
            raise ValueError(f"Template '{data.key}' already exists")
        template = WorkflowTemplate(
            key=data.key,
            name=data.name,
            description=data.description,
            steps=[s.model_dump() for s in data.steps],
            input_schema=data.input_schema,
            is_active=data.is_active,
        )
        return await self.repo.create(template)

    async def update_template(self, key: str, data: WorkflowTemplateUpdate) -> WorkflowTemplate:
        template = await self.get_template(key)
        if data.name is not None:
            template.name = data.name
        if data.description is not None:
            template.description = data.description
        if data.steps is not None:
            template.steps = [s.model_dump() for s in data.steps]
        if data.input_schema is not None:
            template.input_schema = data.input_schema
        if data.is_active is not None:
            template.is_active = data.is_active
        return await self.repo.update(template)

    async def build_plan(
        self,
        parsed: ParsedScenario,
    ) -> tuple[list[PlannedStep], ExecutionPlan]:
        matcher = TemplateMatcher(self.db)
        template_key = await matcher.match(parsed.objective, explicit_key=parsed.template_key)
        strategy = await WorkflowFactory.create(template_key, self.db)
        strategy.bind_inputs(parsed.inputs)
        return strategy.merge(
            [a.model_dump() for a in parsed.business_actions],
            parsed.expected_results,
        )

    async def preview(
        self, key: str, body: WorkflowPreviewRequest
    ) -> tuple[list[PlannedStep], list[str]]:
        strategy = await WorkflowFactory.create(key, self.db)
        strategy.bind_inputs(body.inputs)
        planned, _ = strategy.merge(body.business_actions, body.expected_results)
        return planned, body.expected_results
