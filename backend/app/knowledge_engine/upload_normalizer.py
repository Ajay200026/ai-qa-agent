"""Normalize partial Salesforce folder uploads into a scannable SFDX layout."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.knowledge_engine.repo_path_resolver import find_salesforce_project_root
from app.knowledge_engine.scanner.repo_scanner import _classify_file
from app.knowledge_engine.types import SalesforceFileType

_SKIP_PARTS = {".git", "node_modules", ".sfdx", ".sf", "coverage", ".husky", "_normalized"}


def _has_sfdx_layout(path: Path) -> bool:
    return (path / "sfdx-project.json").is_file() or (path / "force-app").is_dir()


def _has_main_default_layout(path: Path) -> bool:
    return (path / "main" / "default").is_dir()


def _iter_salesforce_files(workspace: Path) -> list[Path]:
    files: list[Path] = []
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_PARTS for part in path.parts):
            continue
        if _classify_file(path) is not None:
            files.append(path)
    return files


def _destination_for_file(
    file_path: Path, file_type: SalesforceFileType, default: Path, rel: Path
) -> Path:
    parts = rel.parts

    if file_type == SalesforceFileType.LWC:
        if "lwc" in parts:
            idx = parts.index("lwc")
            return default / "lwc" / Path(*parts[idx + 1 :])
        return default / "lwc" / rel

    if file_type == SalesforceFileType.APEX_CLASS:
        if "classes" in parts:
            idx = parts.index("classes")
            return default / "classes" / Path(*parts[idx + 1 :])
        return default / "classes" / file_path.name

    if file_type == SalesforceFileType.APEX_TRIGGER:
        if "triggers" in parts:
            idx = parts.index("triggers")
            return default / "triggers" / Path(*parts[idx + 1 :])
        return default / "triggers" / file_path.name

    if file_type == SalesforceFileType.FLOW:
        if "flows" in parts:
            idx = parts.index("flows")
            return default / "flows" / Path(*parts[idx + 1 :])
        return default / "flows" / file_path.name

    if file_type == SalesforceFileType.OBJECT:
        if "objects" in parts:
            idx = parts.index("objects")
            return default / "objects" / Path(*parts[idx + 1 :])
        return default / "objects" / rel

    if file_type == SalesforceFileType.FIELD:
        if "objects" in parts:
            idx = parts.index("objects")
            return default / "objects" / Path(*parts[idx + 1 :])
        return default / "objects" / rel

    if file_type == SalesforceFileType.VALIDATION_RULE:
        if "objects" in parts:
            idx = parts.index("objects")
            return default / "objects" / Path(*parts[idx + 1 :])
        return default / "objects" / rel

    if file_type == SalesforceFileType.LAYOUT:
        if "layouts" in parts:
            idx = parts.index("layouts")
            return default / "layouts" / Path(*parts[idx + 1 :])
        return default / "layouts" / file_path.name

    if file_type == SalesforceFileType.PERMISSION_SET:
        if "permissionsets" in parts:
            idx = parts.index("permissionsets")
            return default / "permissionsets" / Path(*parts[idx + 1 :])
        return default / "permissionsets" / file_path.name

    if file_type == SalesforceFileType.LABEL:
        if "labels" in parts:
            idx = parts.index("labels")
            return default / "labels" / Path(*parts[idx + 1 :])
        return default / "labels" / file_path.name

    if file_type == SalesforceFileType.CUSTOM_METADATA:
        if "customMetadata" in parts:
            idx = parts.index("customMetadata")
            return default / "customMetadata" / Path(*parts[idx + 1 :])
        return default / "customMetadata" / rel

    return default / rel


def _write_minimal_sfdx_project(workspace: Path) -> None:
    sfdx = workspace / "sfdx-project.json"
    if sfdx.exists():
        return
    sfdx.write_text(
        json.dumps({"packageDirectories": [{"path": "force-app", "default": True}]}, indent=2),
        encoding="utf-8",
    )


def _wrap_main_default_as_force_app(workspace: Path) -> None:
    """User uploaded the force-app folder: main/default/... at workspace root."""
    if (workspace / "force-app").exists():
        return
    main_dir = workspace / "main"
    if not main_dir.is_dir():
        return
    force_app = workspace / "force-app"
    force_app.mkdir(parents=True, exist_ok=True)
    shutil.move(str(main_dir), str(force_app / "main"))


def normalize_salesforce_upload(workspace: Path, *, preserve_existing: bool = False) -> Path:
    """
    Accept a full SFDX project or a partial folder (LWC bundles, Apex classes, metadata).
    When preserve_existing=True, never relocate files already under force-app/.
    """
    workspace = workspace.resolve()

    if _has_sfdx_layout(workspace):
        _write_minimal_sfdx_project(workspace)
        return find_salesforce_project_root(workspace)

    if _has_main_default_layout(workspace):
        _wrap_main_default_as_force_app(workspace)
        _write_minimal_sfdx_project(workspace)
        return find_salesforce_project_root(workspace)

    for marker in workspace.rglob("force-app"):
        if marker.is_dir():
            root = find_salesforce_project_root(marker.parent)
            _write_minimal_sfdx_project(root)
            return root

    if preserve_existing and _iter_salesforce_files(workspace):
        default = workspace / "force-app" / "main" / "default"
        if default.is_dir():
            _write_minimal_sfdx_project(workspace)
            return find_salesforce_project_root(workspace)

    salesforce_files = _iter_salesforce_files(workspace)
    if not salesforce_files:
        raise ValueError(
            "No Salesforce code found. Select a folder with LWC (.js, .html), Apex (.cls), "
            "triggers, flows, objects/metadata — or upload the full project root."
        )

    default = workspace / "force-app" / "main" / "default"
    default.mkdir(parents=True, exist_ok=True)

    for file_path in salesforce_files:
        rel = file_path.relative_to(workspace)
        if "force-app" in rel.parts:
            continue

        file_type = _classify_file(file_path)
        if file_type is None:
            continue

        dest = _destination_for_file(file_path, file_type, default, rel)
        if dest.resolve() == file_path.resolve():
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            continue
        shutil.move(str(file_path), str(dest))

    _write_minimal_sfdx_project(workspace)
    return find_salesforce_project_root(workspace)
