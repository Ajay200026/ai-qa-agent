"""Cleanup knowledge repos, modules, workspaces, and graph/vector artifacts."""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.knowledge.neo4j_client import neo4j_client
from app.knowledge_engine.graph_writer import clear_module_graph
from app.knowledge_engine.vector_store import delete_module_vectors
from app.models.knowledge import KnowledgeRepo, RepoSourceType
from app.repositories.azure_devops_repository import AzureDevOpsConnectionRepository
from app.repositories.knowledge_repository import (
    KnowledgeEntityRepository,
    KnowledgeModuleRepository,
    KnowledgeRepoRepository,
)

logger = logging.getLogger(__name__)


async def cleanup_module_artifacts(module_id: UUID) -> None:
    try:
        await clear_module_graph(module_id)
    except Exception:
        logger.exception("Failed to clear Neo4j graph for module %s", module_id)
    try:
        delete_module_vectors(module_id)
    except Exception:
        logger.exception("Failed to clear vectors for module %s", module_id)


async def cleanup_repo_artifacts(
    repo_id: UUID, module_ids: list[UUID], workspace: Path | None
) -> None:
    for module_id in module_ids:
        await cleanup_module_artifacts(module_id)

    if workspace and workspace.exists():
        await asyncio.to_thread(shutil.rmtree, workspace, True)

    try:
        await neo4j_client.run_query(
            "MATCH (n:KeNode {repo_id: $repo_id}) DETACH DELETE n",
            {"repo_id": str(repo_id)},
        )
    except Exception:
        logger.debug("No brain nodes for repo %s", repo_id)


class KnowledgeCleanupService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo_repo = KnowledgeRepoRepository(db)
        self.module_repo = KnowledgeModuleRepository(db)
        self.entity_repo = KnowledgeEntityRepository(db)
        self.connection_repo = AzureDevOpsConnectionRepository(db)

    def _workspace_dir(self, repo: KnowledgeRepo) -> Path | None:
        settings = get_settings()
        if repo.source_type == RepoSourceType.AZURE.value:
            return settings.azure_devops_workspace_dir / str(repo.id)
        if repo.source_type == RepoSourceType.LOCAL.value:
            return settings.local_workspace_dir / str(repo.id)
        return None

    async def delete_module(self, module_id: UUID, owner_id: UUID) -> None:
        module = await self.module_repo.get_with_entities(module_id)
        if not module or not module.repo or module.repo.owner_id != owner_id:
            raise ValueError("Module not found")

        await self.entity_repo.delete_by_module(module_id)
        await self.module_repo.delete(module_id)
        await self.db.commit()

    async def delete_repo(self, repo_id: UUID, owner_id: UUID) -> tuple[list[UUID], Path | None]:
        repo = await self.repo_repo.get_by_id(repo_id)
        if not repo or repo.owner_id != owner_id:
            raise ValueError("Repository not found")

        modules = await self.module_repo.list_by_repo(repo_id)
        module_ids = [module.id for module in modules]
        workspace = self._workspace_dir(repo)

        for module_id in module_ids:
            await self.entity_repo.delete_by_module(module_id)

        await self.module_repo.delete_by_repo(repo_id)
        await self.repo_repo.delete(repo_id)
        await self.db.commit()

        return module_ids, workspace

    async def reset_all(self, owner_id: UUID) -> dict[str, int]:
        repos = await self.repo_repo.list_by_owner(owner_id)
        repo_count = len(repos)
        pending_cleanup: list[tuple[UUID, list[UUID], Path | None]] = []

        for repo in repos:
            module_ids, workspace = await self.delete_repo(repo.id, owner_id)
            pending_cleanup.append((repo.id, module_ids, workspace))

        connections = await self.connection_repo.list_by_owner(owner_id)
        conn_count = len(connections)
        for conn in connections:
            await self.connection_repo.delete(conn)

        await self.db.commit()

        for repo_id, module_ids, workspace in pending_cleanup:
            await cleanup_repo_artifacts(repo_id, module_ids, workspace)

        return {"repos_deleted": repo_count, "connections_deleted": conn_count}
