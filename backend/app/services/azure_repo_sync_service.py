"""Clone or update Azure DevOps repos into local workspace for scanning."""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decrypt_credentials
from app.knowledge_engine.repo_path_resolver import find_salesforce_project_root
from app.models.knowledge import KnowledgeRepo, RepoSourceType
from app.repositories.azure_devops_repository import AzureDevOpsConnectionRepository
from app.repositories.knowledge_repository import KnowledgeRepoRepository
from app.services.azure_devops_service import AzureDevOpsClient, safe_branch_dirname

logger = logging.getLogger(__name__)


class AzureRepoSyncService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo_repo = KnowledgeRepoRepository(db)
        self.connection_repo = AzureDevOpsConnectionRepository(db)

    async def sync_repo(self, repo: KnowledgeRepo) -> Path:
        if repo.source_type != RepoSourceType.AZURE.value:
            raise ValueError("Not an Azure DevOps repository")

        if not repo.azure_connection_id or not repo.azure_project or not repo.azure_repo:
            raise ValueError("Azure repository metadata is incomplete")

        connection = await self.connection_repo.get_by_id(repo.azure_connection_id)
        if not connection:
            raise ValueError("Azure DevOps connection not found")

        pat = decrypt_credentials(connection.encrypted_pat)
        client = AzureDevOpsClient(connection.organization_url, pat)
        branch = repo.branch or "main"
        clone_url = client.build_clone_url(repo.azure_project, repo.azure_repo)

        settings = get_settings()
        workspace_root = settings.azure_devops_workspace_dir
        workspace_root.mkdir(parents=True, exist_ok=True)
        workspace = workspace_root / str(repo.id) / safe_branch_dirname(branch)

        if not (workspace / ".git").is_dir():
            if workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)
            workspace.parent.mkdir(parents=True, exist_ok=True)
            await self._run_git(
                "clone",
                "--branch",
                branch,
                "--single-branch",
                "--depth",
                "1",
                clone_url,
                str(workspace),
            )
        else:
            await self._run_git("-C", str(workspace), "fetch", "origin", branch, "--depth", "1")
            await self._run_git("-C", str(workspace), "checkout", branch)
            await self._run_git("-C", str(workspace), "reset", "--hard", f"origin/{branch}")

        project_root = find_salesforce_project_root(workspace)
        commit = await self._run_git("-C", str(workspace), "rev-parse", "HEAD")
        repo.path = str(project_root)
        repo.last_synced_commit = commit.strip()
        await self.repo_repo.update(repo)
        await self.db.commit()
        logger.info("Synced Azure repo %s@%s -> %s", repo.azure_repo, branch, project_root)
        return project_root

    async def _run_git(self, *args: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            detail = stderr.decode().strip() or stdout.decode().strip()
            raise ValueError(f"Git failed: {detail}")
        return stdout.decode()
