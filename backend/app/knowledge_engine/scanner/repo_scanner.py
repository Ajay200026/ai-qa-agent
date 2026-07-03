"""Discover Salesforce modules and files within a local repository."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.knowledge_engine.types import SalesforceFileType, ScannedFile

METADATA_SUFFIXES = {
    ".cls": SalesforceFileType.APEX_CLASS,
    ".trigger": SalesforceFileType.APEX_TRIGGER,
    ".flow-meta.xml": SalesforceFileType.FLOW,
    ".object-meta.xml": SalesforceFileType.OBJECT,
    ".field-meta.xml": SalesforceFileType.FIELD,
    ".validationRule-meta.xml": SalesforceFileType.VALIDATION_RULE,
    ".layout-meta.xml": SalesforceFileType.LAYOUT,
    ".permissionset-meta.xml": SalesforceFileType.PERMISSION_SET,
    ".labels-meta.xml": SalesforceFileType.LABEL,
}

LWC_FILES = {"html", "js", "js-meta.xml"}


def _classify_file(path: Path) -> SalesforceFileType | None:
    name = path.name
    for suffix, file_type in METADATA_SUFFIXES.items():
        if name.endswith(suffix):
            return file_type
    if path.suffix == ".xml" and "customMetadata" in str(path):
        return SalesforceFileType.CUSTOM_METADATA
    if path.parent.name == "lwc" and path.suffix in {".html", ".js"}:
        return SalesforceFileType.LWC
    if path.parent.parent.name == "lwc" and name.endswith(".js-meta.xml"):
        return SalesforceFileType.LWC
    return None


def find_package_roots(repo_path: Path) -> list[Path]:
    roots: list[Path] = []
    sfdx = repo_path / "sfdx-project.json"
    if sfdx.exists():
        try:
            data = json.loads(sfdx.read_text(encoding="utf-8"))
            for pkg in data.get("packageDirectories", []):
                rel = pkg.get("path", "")
                candidate = repo_path / rel
                if candidate.is_dir():
                    roots.append(candidate)
        except (json.JSONDecodeError, OSError):
            pass
    default = repo_path / "force-app" / "main" / "default"
    if default.is_dir():
        roots.append(default)
    for candidate in repo_path.glob("force-app/*/default"):
        if candidate.is_dir() and candidate not in roots:
            roots.append(candidate)
    if not roots and (repo_path / "src").is_dir():
        roots.append(repo_path / "src")
    return roots or [repo_path]


def enumerate_all_files(repo_path: Path) -> list[ScannedFile]:
    repo_path = repo_path.resolve()
    files: list[ScannedFile] = []
    skip_dirs = {".git", "node_modules", ".sfdx", ".sf", "coverage", ".husky"}

    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        file_type = _classify_file(path)
        if file_type is None:
            continue
        rel = str(path.relative_to(repo_path))
        files.append(ScannedFile(path=path, relative_path=rel, file_type=file_type))
    return files


def _module_matches(path: str, module_name: str) -> bool:
    normalized = module_name.lower().replace(" ", "").replace("_", "").replace("-", "")
    path_lower = path.lower().replace("_", "").replace("-", "")
    if normalized in path_lower:
        return True
    # CamelCase token match: DataChange -> dataChange
    tokens = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)", module_name)
    if tokens:
        camel = tokens[0].lower() + "".join(t.capitalize() for t in tokens[1:])
        if camel in path:
            return True
    return False


def filter_module_files(all_files: list[ScannedFile], module_name: str) -> list[ScannedFile]:
    return [f for f in all_files if _module_matches(f.relative_path, module_name)]


def discover_modules(repo_path: Path) -> list[dict[str, int | str]]:
    """Return candidate module names with approximate file counts."""
    all_files = enumerate_all_files(repo_path)
    counts: dict[str, int] = {}

    for scanned in all_files:
        parts = Path(scanned.relative_path).parts
        for i, part in enumerate(parts):
            if part in {"lwc", "classes", "objects", "flows", "triggers", "aura"}:
                if i + 1 < len(parts):
                    name = parts[i + 1]
                    if not name.endswith("-meta.xml"):
                        counts[name] = counts.get(name, 0) + 1
                break
        # Package-level modules
        if "force-app" in parts:
            idx = parts.index("force-app")
            if idx + 1 < len(parts) and parts[idx + 1] != "main":
                pkg = parts[idx + 1]
                counts[pkg] = counts.get(pkg, 0) + 1

    # Merge similar names (dataChange vs DataChange)
    merged: dict[str, int] = {}
    for name, count in counts.items():
        key = name[0].upper() + name[1:] if name else name
        merged[key] = merged.get(key, 0) + count

    return [{"name": name, "file_count": count} for name, count in sorted(merged.items())]


def resolve_reference_files(
    all_files: list[ScannedFile],
    references: set[str],
    already_indexed: set[str],
) -> list[ScannedFile]:
    """Find repo files matching unresolved references (dependency closure)."""
    found: list[ScannedFile] = []
    refs_lower = {r.lower() for r in references}

    for scanned in all_files:
        if scanned.relative_path in already_indexed:
            continue
        stem = scanned.path.stem.replace("-meta", "")
        name = scanned.path.parent.name if scanned.file_type == SalesforceFileType.LWC else stem
        name_variants = {
            name.lower(),
            stem.lower(),
            name.replace("_", "").lower(),
            stem.replace("_", "").lower(),
        }
        if refs_lower & name_variants:
            found.append(scanned)
            continue
        # Object/field references in path
        for ref in refs_lower:
            if ref in scanned.relative_path.lower():
                found.append(scanned)
                break

    return found


def find_class_file(all_files: list[ScannedFile], class_name: str) -> ScannedFile | None:
    target = class_name.lower()
    for scanned in all_files:
        if scanned.file_type == SalesforceFileType.APEX_CLASS:
            if scanned.path.stem.lower() == target:
                return scanned
    return None


def find_lwc_bundle(all_files: list[ScannedFile], component_name: str) -> list[ScannedFile]:
    target = component_name.lower()
    return [
        f
        for f in all_files
        if f.file_type == SalesforceFileType.LWC
        and f.path.parent.name.lower() == target
    ]
