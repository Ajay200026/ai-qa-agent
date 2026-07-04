"""In-memory upload sessions for batched folder uploads."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

SESSION_TTL_SECONDS = 3600


@dataclass
class UploadedFileRecord:
    file_name: str
    relative_path: str
    full_path: str
    extension: str
    size: int
    salesforce_type: str | None = None


@dataclass
class UploadSession:
    session_id: str
    repo_id: uuid.UUID
    workspace: Path
    name: str
    owner_id: uuid.UUID
    bytes_written: int = 0
    files_written: int = 0
    manifest: list[UploadedFileRecord] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


_sessions: dict[str, UploadSession] = {}


def _cleanup_expired() -> None:
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s.created_at > SESSION_TTL_SECONDS]
    for sid in expired:
        _sessions.pop(sid, None)


def create_session(repo_id: uuid.UUID, workspace: Path, name: str, owner_id: uuid.UUID) -> UploadSession:
    _cleanup_expired()
    session_id = str(uuid.uuid4())
    session = UploadSession(
        session_id=session_id,
        repo_id=repo_id,
        workspace=workspace,
        name=name,
        owner_id=owner_id,
    )
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> UploadSession | None:
    _cleanup_expired()
    return _sessions.get(session_id)


def pop_session(session_id: str) -> UploadSession | None:
    return _sessions.pop(session_id, None)
