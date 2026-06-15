from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.project import Project
from app.models.user import User
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.repo = ProjectRepository(db)

    async def create(self, data: ProjectCreate, owner: User) -> Project:
        project = Project(
            name=data.name,
            description=data.description,
            owner_id=owner.id,
        )
        return await self.repo.create(project)

    async def list_for_user(self, user: User) -> list[Project]:
        return await self.repo.list_by_owner(user.id)

    async def get(self, project_id: UUID) -> Project:
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise NotFoundError("Project", project_id)
        return project
