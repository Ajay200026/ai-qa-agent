from pathlib import Path
from uuid import UUID

from app.core.config import get_settings
from app.core.exceptions import NotFoundError


def artifact_basename(path: str | None) -> str | None:
    if not path:
        return None
    return Path(path).name


def _artifacts_root() -> Path:
    return get_settings().artifacts_dir


def execution_artifacts_dir(execution_id: UUID) -> Path:
    return _artifacts_root() / str(execution_id)


def list_artifact_files(execution_id: UUID) -> list[str]:
    directory = execution_artifacts_dir(execution_id)
    if not directory.is_dir():
        return []
    return sorted(p.name for p in directory.glob("*.png") if p.is_file())


def resolve_artifact_path(execution_id: UUID, filename: str) -> Path:
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        raise NotFoundError("Artifact", filename or "invalid")
    filepath = execution_artifacts_dir(execution_id) / filename
    if not filepath.exists() or not filepath.is_file():
        raise NotFoundError("Artifact", filename)
    return filepath
