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
from app.schemas.scenario import ScenarioCreate


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
            test_case_file=await self._save_upload(test_case_file),
            regression_file=await self._save_upload(regression_file),
        )
        return await self.repo.create(scenario)

    async def get(self, scenario_id: UUID) -> Scenario:
        scenario = await self.repo.get_by_id(scenario_id)
        if not scenario:
            raise NotFoundError("Scenario", scenario_id)
        return scenario

    async def list_by_project(self, project_id: UUID) -> list[Scenario]:
        return await self.repo.list_by_project(project_id)
