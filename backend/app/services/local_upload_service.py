"""Local codebase upload (ZIP and folder) for knowledge repos."""

from __future__ import annotations

import logging
import shutil
import zipfile
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.knowledge_engine.scanner.repo_scanner import _classify_file, _file_type_key
from app.knowledge_engine.upload_normalizer import normalize_salesforce_upload
from app.models.knowledge import KnowledgeRepo, RepoSourceType
from app.repositories.knowledge_repository import KnowledgeRepoRepository
from app.services.upload_session import (
    UploadSession,
    UploadedFileRecord,
    create_session,
    get_session,
    pop_session,
)

logger = logging.getLogger(__name__)

SKIP_UPLOAD_PARTS = {".git", "node_modules", ".sfdx", ".sf", "coverage", ".husky"}
CHUNK_SIZE = 1024 * 1024


def _reject_traversal(name: str) -> None:
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or ".." in normalized.split("/"):
        raise ValueError(f"Invalid path in upload: {name}")


def _should_skip_path(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    return any(part in SKIP_UPLOAD_PARTS for part in parts)


class LocalUploadService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo_repo = KnowledgeRepoRepository(db)

    def _workspace(self, repo_id: UUID) -> Path:
        settings = get_settings()
        path = settings.local_workspace_dir / str(repo_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def _stream_upload_to_disk(
        self, upload: UploadFile, target: Path, settings_limit: int, session_bytes: int
    ) -> tuple[int, int]:
        total = session_bytes
        written = 0
        with target.open("wb") as out:
            while True:
                chunk = await upload.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > settings_limit:
                    raise ValueError("Upload exceeds maximum size (500 MB)")
                out.write(chunk)
                written += len(chunk)
        return written, total

    async def start_folder_session(self, owner_id: UUID, name: str) -> UploadSession:
        repo = KnowledgeRepo(
            name=name.strip(),
            path="",
            source_type=RepoSourceType.LOCAL.value,
            owner_id=owner_id,
        )
        created = await self.repo_repo.create(repo)
        await self.db.flush()
        workspace = self._workspace(created.id)
        return create_session(created.id, workspace, name.strip(), owner_id)

    async def write_batch_files(
        self,
        session: UploadSession,
        files: list[tuple[str, UploadFile]],
    ) -> int:
        settings = get_settings()
        if len(files) > settings.upload_batch_max_files:
            raise ValueError(f"Batch exceeds {settings.upload_batch_max_files} files")

        count = 0
        for rel_path, upload in files:
            rel = rel_path.replace("\\", "/").strip("/")
            if not rel or _should_skip_path(rel):
                continue
            _reject_traversal(rel)
            target = session.workspace / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            written, session.bytes_written = await self._stream_upload_to_disk(
                upload, target, settings.max_upload_bytes, session.bytes_written
            )
            if written == 0:
                continue
            file_type = _classify_file(target)
            session.manifest.append(
                UploadedFileRecord(
                    file_name=target.name,
                    relative_path=rel,
                    full_path=str(target),
                    extension=target.suffix,
                    size=written,
                    salesforce_type=_file_type_key(file_type) if file_type else None,
                )
            )
            session.files_written += 1
            count += 1
        return count

    async def finalize_folder_session(self, session_id: str, owner_id: UUID) -> dict:
        session = get_session(session_id)
        if not session or session.owner_id != owner_id:
            raise ValueError("Upload session not found")

        if session.files_written == 0:
            raise ValueError("No files were uploaded")

        repo = await self.repo_repo.get_by_id(session.repo_id)
        if not repo or repo.owner_id != owner_id:
            raise ValueError("Repository not found")

        try:
            sfdx_root = normalize_salesforce_upload(session.workspace, preserve_existing=True)
            repo.path = str(sfdx_root)
            repo.name = session.name
            await self.db.commit()
            await self.db.refresh(repo)
        except Exception:
            shutil.rmtree(session.workspace, ignore_errors=True)
            await self.repo_repo.delete(session.repo_id)
            await self.db.commit()
            pop_session(session_id)
            raise

        pop_session(session_id)
        uploaded_files = [
            {"path": r.relative_path, "type": r.salesforce_type or "other", "size": r.size}
            for r in session.manifest
        ]
        return {
            "success": True,
            "projectName": repo.name,
            "totalFiles": session.files_written,
            "uploadedFiles": uploaded_files,
            "repo": repo,
        }

    async def create_from_zip(self, owner_id: UUID, name: str, upload: UploadFile) -> KnowledgeRepo:
        settings = get_settings()
        repo = KnowledgeRepo(
            name=name.strip(),
            path="",
            source_type=RepoSourceType.LOCAL.value,
            owner_id=owner_id,
        )
        created = await self.repo_repo.create(repo)
        await self.db.flush()

        workspace = self._workspace(created.id)
        zip_path = workspace / "_upload.zip"
        total = 0

        try:
            with zip_path.open("wb") as out:
                while True:
                    chunk = await upload.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > settings.max_upload_bytes:
                        raise ValueError("Upload exceeds maximum size (500 MB)")
                    out.write(chunk)

            with zipfile.ZipFile(zip_path, "r") as zf:
                for info in zf.infolist():
                    _reject_traversal(info.filename)
                    if info.is_dir() or _should_skip_path(info.filename):
                        continue
                    target = workspace / info.filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, target.open("wb") as dst:
                        shutil.copyfileobj(src, dst)

            zip_path.unlink(missing_ok=True)
            sfdx_root = normalize_salesforce_upload(workspace, preserve_existing=True)
            created.path = str(sfdx_root)
            await self.db.commit()
            await self.db.refresh(created)
            return created
        except Exception:
            shutil.rmtree(workspace, ignore_errors=True)
            await self.repo_repo.delete(created.id)
            await self.db.commit()
            raise

    async def create_from_files(
        self, owner_id: UUID, name: str, files: list[tuple[str, UploadFile]]
    ) -> KnowledgeRepo:
        session = await self.start_folder_session(owner_id, name)
        await self.write_batch_files(session, files)
        result = await self.finalize_folder_session(session.session_id, owner_id)
        return result["repo"]
