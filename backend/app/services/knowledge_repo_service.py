"""Knowledge repository and module management."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_engine.brain_graph_writer import write_repository_node
from app.knowledge_engine.repo_path_resolver import find_salesforce_project_root
from app.knowledge_engine.scanner.repo_scanner import (
    discover_feature_scopes,
    discover_modules,
    list_repo_children,
    module_display_name,
    normalize_scope_path,
    preflight_scope_files,
    resolve_scan_root,
    validate_scope_path,
)
from app.knowledge_engine.vector_store import vector_status
from app.models.knowledge import KnowledgeModule, KnowledgeRepo, RepoSourceType, ScanStatus
from app.repositories.azure_devops_repository import AzureDevOpsConnectionRepository
from app.repositories.knowledge_repository import KnowledgeModuleRepository, KnowledgeRepoRepository
from app.schemas.knowledge_engine import (
    DiscoveredModule,
    KnowledgeRepoCreate,
    ModuleStatusResponse,
    RepoFileEntry,
    RepoFolderEntry,
    FileContentResponse,
    ValidateScopeResponse,
)
from app.services.azure_repo_sync_service import AzureRepoSyncService

ALLOWED_EXTENSIONS = {
    ".cls", ".trigger", ".js", ".html", ".xml", ".json", ".css", ".md", ".yaml", ".yml",
}
MAX_FILE_BYTES = 512_000


def _safe_resolve_path(repo_root: Path, relative: str) -> Path:
    """Resolve relative path within repo root; reject traversal."""
    rel = relative.replace("\\", "/").strip("/")
    if ".." in rel.split("/"):
        raise ValueError("Invalid path")
    target = (repo_root / rel).resolve()
    root_resolved = repo_root.resolve()
    if not str(target).startswith(str(root_resolved)):
        raise ValueError("Path escapes repository root")
    return target


def _detect_language(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".cls") or name.endswith(".trigger"):
        return "apex"
    if name.endswith(".js"):
        return "javascript"
    if name.endswith(".html"):
        return "html"
    if name.endswith(".xml"):
        return "xml"
    if name.endswith(".json"):
        return "json"
    if name.endswith(".css"):
        return "css"
    return "text"


def _is_allowed_file(path: Path) -> bool:
    if path.is_dir():
        return True
    name = path.name.lower()
    for ext in ALLOWED_EXTENSIONS:
        if name.endswith(ext):
            return True
    return False


class KnowledgeRepoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo_repo = KnowledgeRepoRepository(db)
        self.module_repo = KnowledgeModuleRepository(db)
        self.connection_repo = AzureDevOpsConnectionRepository(db)

    async def create_repo(self, owner_id: UUID, body: KnowledgeRepoCreate) -> KnowledgeRepo:
        if body.source_type == RepoSourceType.AZURE.value:
            return await self._create_azure_repo(owner_id, body)
        if body.source_type == RepoSourceType.LOCAL.value and body.path:
            return await self._create_local_repo(owner_id, body)
        raise ValueError("Use Azure DevOps or upload a codebase ZIP/folder.")

    async def _create_local_repo(self, owner_id: UUID, body: KnowledgeRepoCreate) -> KnowledgeRepo:
        path = Path(body.path)
        if not path.is_dir():
            raise ValueError(f"Repository path not found: {body.path}")
        sfdx_root = resolve_scan_root(path)
        repo = KnowledgeRepo(
            name=body.name,
            path=str(sfdx_root),
            source_type=RepoSourceType.LOCAL.value,
            owner_id=owner_id,
        )
        created = await self.repo_repo.create(repo)
        await self.db.commit()
        try:
            await write_repository_node(created)
        except Exception:
            pass
        return created

    async def _create_azure_repo(
        self, owner_id: UUID, body: KnowledgeRepoCreate
    ) -> KnowledgeRepo:
        conn = await self.connection_repo.get_owned(body.connection_id, owner_id)
        if not conn:
            raise ValueError("Azure DevOps connection not found")

        repo = KnowledgeRepo(
            name=body.name,
            path="",
            source_type=RepoSourceType.AZURE.value,
            azure_connection_id=body.connection_id,
            azure_project=body.azure_project,
            azure_repo=body.azure_repo,
            azure_repo_id=body.azure_repo_id,
            branch=body.branch,
            owner_id=owner_id,
        )
        created = await self.repo_repo.create(repo)
        await self.db.commit()

        sync = AzureRepoSyncService(self.db)
        await sync.sync_repo(created)
        refreshed = await self.repo_repo.get_by_id(created.id)
        created = refreshed or created

        try:
            await write_repository_node(created)
        except Exception:
            pass
        return created

    async def ensure_repo_path(self, repo: KnowledgeRepo) -> Path:
        if repo.source_type == RepoSourceType.AZURE.value:
            path = Path(repo.path) if repo.path else None
            if path is None or not path.is_dir():
                sync = AzureRepoSyncService(self.db)
                path = await sync.sync_repo(repo)
            return resolve_scan_root(path)
        if not repo.path:
            raise ValueError("Repository path is not set")
        path = Path(repo.path)
        if not path.is_dir():
            raise ValueError(f"Repository path not found: {repo.path}")
        return resolve_scan_root(path)

    async def list_repos(self, owner_id: UUID) -> list[KnowledgeRepo]:
        return await self.repo_repo.list_by_owner(owner_id)

    async def get_repo(self, repo_id: UUID) -> KnowledgeRepo | None:
        return await self.repo_repo.get_by_id(repo_id)

    async def discover_modules(self, repo_id: UUID, owner_id: UUID | None = None) -> list[DiscoveredModule]:
        if owner_id:
            repo = await self._get_owned_repo(repo_id, owner_id)
        else:
            repo = await self.repo_repo.get_by_id(repo_id)
        if not repo:
            raise ValueError("Repository not found")
        repo_path = await self.ensure_repo_path(repo)
        modules = discover_feature_scopes(repo_path)
        return [DiscoveredModule(**m) for m in modules]

    async def validate_scope(
        self, repo_id: UUID, owner_id: UUID, scope_path: str
    ) -> ValidateScopeResponse:
        repo = await self._get_owned_repo(repo_id, owner_id)
        repo_path = await self.ensure_repo_path(repo)
        result = validate_scope_path(repo_path, scope_path)
        return ValidateScopeResponse(**result)

    async def list_repo_tree(self, repo_id: UUID, path: str = "") -> list[RepoFolderEntry]:
        repo = await self.repo_repo.get_by_id(repo_id)
        if not repo:
            raise ValueError("Repository not found")
        repo_path = await self.ensure_repo_path(repo)
        entries = list_repo_children(repo_path, path)
        return [RepoFolderEntry(**e) for e in entries]

    async def create_module(
        self, repo_id: UUID, name: str, scope_path: str | None = None, owner_id: UUID | None = None
    ) -> KnowledgeModule:
        if owner_id:
            repo = await self._get_owned_repo(repo_id, owner_id)
        else:
            repo = await self.repo_repo.get_by_id(repo_id)
        if not repo:
            raise ValueError("Repository not found")
        repo_path = await self.ensure_repo_path(repo)
        normalized_scope = normalize_scope_path(repo_path, scope_path) if scope_path else None
        if normalized_scope:
            validation = validate_scope_path(repo_path, normalized_scope)
            if not validation["valid"]:
                msg = validation.get("message") or "Invalid module scope"
                suggestion = validation.get("suggestion")
                if suggestion:
                    msg += f" Try: {suggestion}"
                raise ValueError(msg)
            normalized_scope = validation.get("normalized_path") or normalized_scope
        display_name = module_display_name(normalized_scope) if normalized_scope else name
        module = KnowledgeModule(
            repo_id=repo_id,
            name=display_name,
            scope_path=normalized_scope,
            scan_status=ScanStatus.PENDING.value,
        )
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

    async def _get_owned_repo(self, repo_id: UUID, owner_id: UUID) -> KnowledgeRepo:
        repo = await self.repo_repo.get_by_id(repo_id)
        if not repo or repo.owner_id != owner_id:
            raise ValueError("Repository not found")
        return repo

    async def list_repo_files(
        self,
        repo_id: UUID,
        owner_id: UUID,
        path: str = "",
        scope_path: str | None = None,
    ) -> list[RepoFileEntry]:
        repo = await self._get_owned_repo(repo_id, owner_id)
        repo_path = await self.ensure_repo_path(repo)
        base = repo_path
        if scope_path:
            base = _safe_resolve_path(repo_path, scope_path)
            if not base.is_dir():
                raise ValueError("Scope path is not a directory")
        target = _safe_resolve_path(base, path) if path else base
        if not target.is_dir():
            raise ValueError("Not a directory")

        entries: list[RepoFileEntry] = []
        for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.name.startswith("."):
                continue
            if not _is_allowed_file(child):
                continue
            rel = child.relative_to(repo_path).as_posix()
            entries.append(
                RepoFileEntry(
                    name=child.name,
                    path=rel,
                    is_directory=child.is_dir(),
                    size=child.stat().st_size if child.is_file() else None,
                )
            )
        return entries

    async def read_repo_file(
        self, repo_id: UUID, owner_id: UUID, path: str
    ) -> FileContentResponse:
        repo = await self._get_owned_repo(repo_id, owner_id)
        repo_path = await self.ensure_repo_path(repo)
        target = _safe_resolve_path(repo_path, path)
        if not target.is_file():
            raise ValueError("File not found")
        if not _is_allowed_file(target):
            raise ValueError("File type not allowed")

        size = target.stat().st_size
        truncated = size > MAX_FILE_BYTES
        read_size = min(size, MAX_FILE_BYTES)
        content = target.read_text(encoding="utf-8", errors="replace")[:read_size]
        if truncated:
            content += "\n\n// ... truncated ..."

        return FileContentResponse(
            path=path,
            content=content,
            language=_detect_language(target),
            size=size,
            truncated=truncated,
        )
