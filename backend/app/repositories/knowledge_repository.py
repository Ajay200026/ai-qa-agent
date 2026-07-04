from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.knowledge import KnowledgeEntity, KnowledgeModule, KnowledgeRepo, ScanStatus
from app.repositories.base import BaseRepository


class KnowledgeRepoRepository(BaseRepository[KnowledgeRepo]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, KnowledgeRepo)

    async def list_by_owner(self, owner_id: UUID) -> list[KnowledgeRepo]:
        result = await self.db.execute(
            select(KnowledgeRepo)
            .where(KnowledgeRepo.owner_id == owner_id)
            .order_by(KnowledgeRepo.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete(self, repo_id: UUID) -> None:
        await self.db.execute(delete(KnowledgeRepo).where(KnowledgeRepo.id == repo_id))
        await self.db.flush()


class KnowledgeModuleRepository(BaseRepository[KnowledgeModule]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, KnowledgeModule)

    async def get_with_entities(self, module_id: UUID) -> KnowledgeModule | None:
        result = await self.db.execute(
            select(KnowledgeModule)
            .options(selectinload(KnowledgeModule.entities), selectinload(KnowledgeModule.repo))
            .where(KnowledgeModule.id == module_id)
        )
        return result.scalar_one_or_none()

    async def list_by_repo(self, repo_id: UUID) -> list[KnowledgeModule]:
        result = await self.db.execute(
            select(KnowledgeModule)
            .where(KnowledgeModule.repo_id == repo_id)
            .order_by(KnowledgeModule.name)
        )
        return list(result.scalars().all())

    async def delete(self, module_id: UUID) -> None:
        await self.db.execute(delete(KnowledgeModule).where(KnowledgeModule.id == module_id))
        await self.db.flush()

    async def delete_by_repo(self, repo_id: UUID) -> None:
        await self.db.execute(delete(KnowledgeModule).where(KnowledgeModule.repo_id == repo_id))
        await self.db.flush()

    async def update_status(
        self,
        module: KnowledgeModule,
        *,
        status: ScanStatus,
        error: str | None = None,
        stats: dict | None = None,
    ) -> KnowledgeModule:
        module.scan_status = status.value
        module.scan_error = error
        if stats is not None:
            module.stats = stats
        await self.db.flush()
        await self.db.refresh(module)
        return module


class KnowledgeEntityRepository(BaseRepository[KnowledgeEntity]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, KnowledgeEntity)

    async def list_by_module(self, module_id: UUID) -> list[KnowledgeEntity]:
        result = await self.db.execute(
            select(KnowledgeEntity)
            .where(KnowledgeEntity.module_id == module_id)
            .order_by(KnowledgeEntity.entity_type, KnowledgeEntity.name)
        )
        return list(result.scalars().all())

    async def delete_by_module(self, module_id: UUID) -> None:
        await self.db.execute(
            delete(KnowledgeEntity).where(KnowledgeEntity.module_id == module_id)
        )
        await self.db.flush()

    async def bulk_create(self, entities: list[KnowledgeEntity]) -> list[KnowledgeEntity]:
        self.db.add_all(entities)
        await self.db.flush()
        for entity in entities:
            await self.db.refresh(entity)
        return entities

    async def search_by_name(self, module_id: UUID, name: str) -> list[KnowledgeEntity]:
        pattern = f"%{name}%"
        result = await self.db.execute(
            select(KnowledgeEntity).where(
                KnowledgeEntity.module_id == module_id,
                KnowledgeEntity.name.ilike(pattern),
            )
        )
        return list(result.scalars().all())
