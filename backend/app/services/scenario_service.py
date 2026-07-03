import uuid
from pathlib import Path
from uuid import UUID

import aiofiles
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession



from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.models.scenario import Scenario
from app.repositories.scenario_repository import ScenarioRepository
from app.models.execution import Execution, ExecutionStatus
from app.schemas.scenario import ScenarioCreate, ScenarioUpdate
from app.schemas.login_as import IdentityMap, LoginAsTarget
from app.core.exceptions import BadRequestError
from sqlalchemy import select


class ScenarioService:
    def __init__(self, db: AsyncSession):
        self.repo = ScenarioRepository(db)
        self.settings = get_settings()

    async def _save_upload(self, file: UploadFile | None) -> str | None:
        if not file or not file.filename:
            return None
        self.settings.upload_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(file.filename).suffix
        filename = f"{uuid.uuid4()}{ext}"
        filepath = self.settings.upload_dir / filename
        async with aiofiles.open(filepath, "wb") as f:
            content = await file.read()
            await f.write(content)
        return str(filepath)

    async def create(
        self,
        data: ScenarioCreate,
        test_case_file: UploadFile | None = None,
        regression_file: UploadFile | None = None,
    ) -> Scenario:
        scenario = Scenario(
            project_id=data.project_id,
            name=data.name,
            description=data.description,
            acceptance_criteria=data.acceptance_criteria,
            template_key=data.template_key,
            inputs=data.inputs,
            business_actions=data.business_actions,
            expected_results=data.expected_results,
            test_pack_content=data.test_pack_content,
            customer_target=data.customer_target.model_dump(mode="json") if data.customer_target else None,
            login_as_target=data.login_as_target.model_dump(mode="json") if data.login_as_target else None,
            identity_map=data.identity_map.model_dump(mode="json") if data.identity_map else None,
            account_query_id=data.account_query_id,
            login_as_profile_id=data.login_as_profile_id,
            test_case_file=await self._save_upload(test_case_file),
            regression_file=await self._save_upload(regression_file),
        )
        return await self.repo.create(scenario)

    async def update(self, scenario_id: UUID, data: ScenarioUpdate) -> Scenario:
        scenario = await self.get(scenario_id)

        active = await self.repo.db.execute(
            select(Execution.id)
            .where(Execution.scenario_id == scenario_id)
            .where(Execution.status.in_([ExecutionStatus.RUNNING, ExecutionStatus.QUEUED]))
            .limit(1)
        )
        if active.scalar_one_or_none():
            raise BadRequestError("Cannot edit a scenario with an active execution")

        payload = data.model_dump(exclude_unset=True)
        if "customer_target" in payload:
            ct = data.customer_target
            payload["customer_target"] = ct.model_dump(mode="json") if ct else None
        if "login_as_target" in payload:
            lat = data.login_as_target
            payload["login_as_target"] = lat.model_dump(mode="json") if lat else None
        if "identity_map" in payload:
            imap = data.identity_map
            payload["identity_map"] = imap.model_dump(mode="json") if imap else None
        for key, value in payload.items():
            setattr(scenario, key, value)
        await self.repo.db.flush()
        await self.repo.db.refresh(scenario)
        return scenario

    async def get(self, scenario_id: UUID) -> Scenario:
        scenario = await self.repo.get_by_id(scenario_id)
        if not scenario:
            raise NotFoundError("Scenario", scenario_id)
        return scenario

    async def list_by_project(self, project_id: UUID) -> list[Scenario]:
        return await self.repo.list_by_project(project_id)
