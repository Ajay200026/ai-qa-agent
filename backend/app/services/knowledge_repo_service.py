"""Knowledge repository and module management."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_engine.scanner.repo_scanner import discover_modules
from app.knowledge_engine.vector_store import vector_status
from app.models.knowledge import KnowledgeModule, KnowledgeRepo, ScanStatus
from app.repositories.knowledge_repository import KnowledgeModuleRepository, KnowledgeRepoRepository
from app.schemas.knowledge_engine import DiscoveredModule, ModuleStatusResponse


class KnowledgeRepoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo_repo = KnowledgeRepoRepository(db)
        self.module_repo = KnowledgeModuleRepository(db)

    async def create_repo(self, owner_id: UUID, name: str, path: str) -> KnowledgeRepo:
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_dir():
            raise ValueError(f"Path does not exist or is not a directory: {path}")
        repo = KnowledgeRepo(name=name, path=str(resolved), owner_id=owner_id)
        return await self.repo_repo.create(repo)

    async def list_repos(self, owner_id: UUID) -> list[KnowledgeRepo]:
        return await self.repo_repo.list_by_owner(owner_id)

    async def get_repo(self, repo_id: UUID) -> KnowledgeRepo | None:
        return await self.repo_repo.get_by_id(repo_id)

    async def discover_modules(self, repo_id: UUID) -> list[DiscoveredModule]:
        repo = await self.repo_repo.get_by_id(repo_id)
        if not repo:
            raise ValueError("Repository not found")
        modules = discover_modules(Path(repo.path))
        return [DiscoveredModule(**m) for m in modules]

    async def create_module(self, repo_id: UUID, name: str) -> KnowledgeModule:
        repo = await self.repo_repo.get_by_id(repo_id)
        if not repo:
            raise ValueError("Repository not found")
        module = KnowledgeModule(repo_id=repo_id, name=name, scan_status=ScanStatus.PENDING.value)
        return await self.module_repo.create(module)

    async def list_modules(self, repo_id: UUID) -> list[KnowledgeModule]:
        return await self.module_repo.list_by_repo(repo_id)

    async def get_module_status(self, module_id: UUID) -> ModuleStatusResponse:
        module = await self.module_repo.get_with_entities(module_id)
        if not module:
            raise ValueError("Module not found")
        stats = module.stats or {}
        return ModuleStatusResponse(
            module_id=module.id,
            scan_status=module.scan_status,
            scan_error=module.scan_error,
            stats=stats,
            graph_status=stats.get("graph_status", "pending"),
            vector_status=stats.get("vector_status", vector_status(module_id)),
            ai_status=stats.get("ai_status", "pending"),
        )
