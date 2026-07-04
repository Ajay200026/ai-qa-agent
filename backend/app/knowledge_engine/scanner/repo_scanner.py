"""Discover Salesforce modules and files within a local repository."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.knowledge_engine.repo_path_resolver import find_salesforce_project_root
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


def _looks_like_lwc_bundle(path: Path) -> bool:
    parent = path.parent
    if path.name.endswith(".js-meta.xml"):
        return True
    if path.suffix in {".html", ".js", ".css"}:
        return any(parent.glob("*.js-meta.xml"))
    return False


def _classify_file(path: Path) -> SalesforceFileType | None:
    name = path.name
    for suffix, file_type in METADATA_SUFFIXES.items():
        if name.endswith(suffix):
            return file_type
    if path.suffix == ".xml" and "customMetadata" in str(path):
        return SalesforceFileType.CUSTOM_METADATA
    if _looks_like_lwc_bundle(path):
        return SalesforceFileType.LWC
    parts = path.parts
    if "lwc" in parts:
        if path.suffix in {".html", ".js"} or name.endswith(".js-meta.xml"):
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


def _normalize_match_text(value: str) -> str:
    return value.lower().replace(" ", "").replace("_", "").replace("-", "")


def _module_matches(path: str, module_name: str) -> bool:
    normalized = _normalize_match_text(module_name)
    path_lower = _normalize_match_text(path)
    if normalized in path_lower:
        return True
    # CamelCase token match: DataChange -> dataChange
    tokens = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)", module_name)
    if tokens:
        camel = tokens[0].lower() + "".join(t.capitalize() for t in tokens[1:])
        if camel in path:
            return True
    return False


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def _force_app_tail(path: str) -> str:
    """Path from force-app/ onward — ignores repo or clone folder prefixes."""
    normalized = _normalize_path(path)
    marker = normalized.find("force-app/")
    if marker >= 0:
        return normalized[marker:]
    return normalized


def _file_type_key(file_type: SalesforceFileType) -> str:
    mapping = {
        SalesforceFileType.APEX_CLASS: "apex_class",
        SalesforceFileType.APEX_TRIGGER: "apex_trigger",
        SalesforceFileType.LWC: "lwc",
        SalesforceFileType.FLOW: "flow",
        SalesforceFileType.OBJECT: "object",
        SalesforceFileType.FIELD: "field",
        SalesforceFileType.VALIDATION_RULE: "validation_rule",
        SalesforceFileType.LAYOUT: "layout",
        SalesforceFileType.PERMISSION_SET: "permission_set",
        SalesforceFileType.LABEL: "label",
        SalesforceFileType.CUSTOM_METADATA: "custom_metadata",
    }
    return mapping.get(file_type, "other")


def summarize_folder(repo_path: Path, folder_path: str, all_files: list[ScannedFile] | None = None) -> dict[str, int]:
    """Count Salesforce files under a folder path, grouped by type."""
    repo_path = repo_path.resolve()
    prefix = _normalize_path(folder_path)
    if all_files is None:
        all_files = enumerate_all_files(repo_path)

    breakdown: dict[str, int] = {}
    for scanned in all_files:
        rel = _normalize_path(scanned.relative_path)
        if prefix:
            if not (rel == prefix or rel.startswith(prefix + "/")):
                continue
        key = _file_type_key(scanned.file_type)
        breakdown[key] = breakdown.get(key, 0) + 1
    return breakdown


def list_repo_children(repo_path: Path, parent_path: str = "") -> list[dict[str, int | str | dict[str, int] | bool]]:
    """List immediate child folders under parent_path with file summaries."""
    scan_root = resolve_scan_root(repo_path)
    parent = _normalize_path(parent_path)
    all_files = enumerate_all_files(scan_root)

    if not parent:
        entries: list[dict[str, int | str | dict[str, int] | bool]] = []
        seen: set[str] = set()
        for root in find_package_roots(scan_root):
            rel = _normalize_path(str(root.relative_to(scan_root)))
            if rel in seen:
                continue
            seen.add(rel)
            breakdown = summarize_folder(scan_root, rel, all_files)
            entries.append(
                {
                    "name": root.name if rel else scan_root.name,
                    "path": rel,
                    "file_count": sum(breakdown.values()),
                    "breakdown": breakdown,
                    "is_selectable": False,
                    "is_current": False,
                }
            )
        return sorted(entries, key=lambda e: str(e["path"]))

    parent_dir = scan_root / Path(parent)
    if not parent_dir.is_dir():
        return []

    children: list[dict[str, int | str | dict[str, int] | bool]] = []
    has_child_dirs = False
    try:
        for child in sorted(parent_dir.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith(".") or child.name in {".git", "node_modules", ".sfdx", ".sf"}:
                continue
            has_child_dirs = True
            rel = _normalize_path(str(child.relative_to(scan_root)))
            breakdown = summarize_folder(scan_root, rel, all_files)
            has_subdirs = any(item.is_dir() for item in child.iterdir())
            if not breakdown and not has_subdirs:
                continue
            children.append(
                {
                    "name": child.name,
                    "path": rel,
                    "file_count": sum(breakdown.values()),
                    "breakdown": breakdown,
                    "is_selectable": False,
                    "is_current": False,
                }
            )
    except OSError:
        return []

    if not children and not has_child_dirs:
        breakdown = summarize_folder(scan_root, parent, all_files)
        file_count = sum(breakdown.values())
        if file_count > 0:
            children.append(
                {
                    "name": parent_dir.name,
                    "path": parent,
                    "file_count": file_count,
                    "breakdown": breakdown,
                    "is_selectable": True,
                    "is_current": True,
                }
            )

    return children


def resolve_scan_root(repo_path: Path) -> Path:
    """SFDX project root used as the base for tree paths and file enumeration."""
    return find_salesforce_project_root(repo_path.resolve())


def normalize_scope_path(repo_path: Path, scope_path: str | None) -> str | None:
    """Normalize a stored scope path to be relative to the SFDX project root."""
    return repair_scope_path(repo_path, scope_path)


def repair_scope_path(repo_path: Path, scope_path: str | None) -> str | None:
    """Normalize a stored scope path to be relative to the SFDX project root."""
    if not scope_path:
        return None
    scope = _normalize_path(scope_path)
    root = resolve_scan_root(repo_path)
    try:
        rel_root = _normalize_path(str(root.relative_to(repo_path.resolve())))
        if rel_root and (scope == rel_root or scope.startswith(rel_root + "/")):
            scope = scope[len(rel_root) + 1 :] if scope.startswith(rel_root + "/") else scope
    except ValueError:
        pass
    root_name = root.name
    if scope.startswith(root_name + "/"):
        scope = scope[len(root_name) + 1 :]
    # Strip clone/workspace folder prefix before force-app (e.g. "CoreFlex Onboarding/force-app/...")
    scope = _force_app_tail(scope)
    return scope or None


def preflight_scope_files(
    repo_path: Path,
    module_name: str,
    scope_path: str | None,
) -> tuple[list[ScannedFile], str | None]:
    """Match Salesforce files for a module scope; return files and normalized scope_path."""
    scan_root = resolve_scan_root(repo_path)
    all_files = enumerate_all_files(scan_root)
    repaired_scope = repair_scope_path(repo_path, scope_path) if scope_path else None
    matched = filter_module_files(
        all_files,
        module_name,
        repaired_scope or scope_path,
        scan_root,
    )
    return matched, repaired_scope


GENERIC_FOLDER_NAMES = frozenset(
    {"lwc", "classes", "objects", "flows", "triggers", "aura", "main", "default", "force-app"}
)


def module_display_name(scope_path: str) -> str:
    """Human-readable module label from a folder scope path."""
    parts = [p for p in _normalize_path(scope_path).split("/") if p]
    for part in reversed(parts):
        if part not in GENERIC_FOLDER_NAMES:
            return part
    return parts[-1] if parts else "module"


def _scope_path_matches(relative_path: str, scope_path: str) -> bool:
    rel_tail = _force_app_tail(relative_path)
    scope_tail = _force_app_tail(scope_path)
    if rel_tail == scope_tail or rel_tail.startswith(scope_tail + "/"):
        return True
    rel = _normalize_path(relative_path)
    scope = _normalize_path(scope_path)
    return rel == scope or rel.startswith(scope + "/")


def filter_module_files(
    all_files: list[ScannedFile],
    module_name: str,
    scope_path: str | None = None,
    repo_path: Path | None = None,
) -> list[ScannedFile]:
    if scope_path:
        scope = _normalize_path(scope_path)
        if repo_path is not None:
            normalized = repair_scope_path(repo_path, scope)
            if normalized:
                scope = normalized
        return [f for f in all_files if _scope_path_matches(f.relative_path, scope)]
    return [f for f in all_files if _module_matches(f.relative_path, module_name)]


def discover_modules(repo_path: Path) -> list[dict[str, int | str]]:
    """Return candidate module names with approximate file counts (legacy)."""
    return discover_feature_scopes(repo_path)


def discover_feature_scopes(repo_path: Path) -> list[dict[str, int | str]]:
    """Return feature folders with full scope_path and file counts."""
    scan_root = resolve_scan_root(repo_path)
    candidates: dict[str, int] = {}

    for dirpath in scan_root.rglob("*"):
        if not dirpath.is_dir() or dirpath.name.startswith("."):
            continue
        folder_name = dirpath.name.lower()
        if folder_name in GENERIC_FOLDER_NAMES:
            continue
        try:
            rel = dirpath.relative_to(scan_root).as_posix()
        except ValueError:
            continue
        matched, _ = preflight_scope_files(repo_path, dirpath.name, rel)
        count = len(matched)
        if count < 1:
            continue
        display = module_display_name(rel)
        existing = candidates.get(rel, 0)
        if count > existing:
            candidates[rel] = count
        for other_path, other_count in list(candidates.items()):
            if other_path != rel and (rel.startswith(other_path + "/") or other_path.startswith(rel + "/")):
                parent, child = (other_path, rel) if len(other_path) < len(rel) else (rel, other_path)
                if child.startswith(parent + "/") and candidates.get(parent, 0) <= candidates.get(child, 0):
                    candidates.pop(parent, None)

    results = [
        {"name": module_display_name(scope), "scope_path": scope, "file_count": count}
        for scope, count in sorted(candidates.items(), key=lambda x: (-x[1], x[0]))
    ]
    return results[:50]


def validate_scope_path(repo_path: Path, scope_path: str) -> dict[str, object]:
    """Validate a module scope and suggest fixes when invalid."""
    from collections import Counter

    display_name = module_display_name(scope_path) if scope_path else "module"
    matched, repaired = preflight_scope_files(repo_path, display_name, scope_path)
    file_count = len(matched)
    breakdown: dict[str, int] = dict(Counter(f.file_type.value for f in matched))

    normalized = repaired or normalize_scope_path(repo_path, scope_path)
    folder_name = Path(scope_path.replace("\\", "/").rstrip("/")).name.lower()

    if file_count > 0:
        return {
            "valid": True,
            "normalized_path": normalized,
            "file_count": file_count,
            "breakdown": breakdown,
            "suggestion": None,
            "message": None,
        }

    suggestion: str | None = None
    message = f"No Salesforce files matched scope '{scope_path}'."

    if folder_name in GENERIC_FOLDER_NAMES:
        message = (
            f"'{Path(scope_path).name}' is a generic container folder. "
            "Select a named feature folder (e.g. Data Change) instead."
        )
        children = list_repo_children(repo_path, scope_path)
        for child in children:
            if child["name"].lower() in GENERIC_FOLDER_NAMES:
                continue
            child_matched, child_repaired = preflight_scope_files(
                repo_path, child["name"], child["path"]
            )
            if child_matched:
                suggestion = child_repaired or child["path"]
                message = f"Select '{child['name']}' instead of '{Path(scope_path).name}'."
                break

    if not suggestion and normalized:
        parent = str(Path(normalized).parent).replace("\\", "/")
        if parent and parent != ".":
            parent_matched, parent_repaired = preflight_scope_files(repo_path, display_name, parent)
            if parent_matched:
                suggestion = parent_repaired or parent
                message = f"Try parent folder '{Path(parent).name}' instead."

    return {
        "valid": False,
        "normalized_path": normalized,
        "file_count": 0,
        "breakdown": breakdown,
        "suggestion": suggestion,
        "message": message,
    }


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
