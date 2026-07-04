"""Helpers for Salesforce project roots inside synced workspaces."""

from __future__ import annotations

from pathlib import Path

_SKIP_SEARCH_DIRS = {".git", "node_modules", ".sfdx", ".sf", "coverage", ".husky"}


def _has_sfdx_marker(directory: Path) -> bool:
    return (directory / "sfdx-project.json").is_file() or (directory / "force-app").is_dir()


def find_salesforce_project_root(path: Path) -> Path:
    """Walk up from a file or folder until the SFDX project root is found."""
    current = path.resolve()
    if current.is_file():
        current = current.parent

    for candidate in [current, *current.parents]:
        if _has_sfdx_marker(candidate):
            return candidate

    # Azure/git clones often nest the SFDX project one or more levels below the workspace root
    # (e.g. workspace/CoreFlex Onboarding/force-app/...).
    if current.is_dir():
        queue: list[tuple[Path, int]] = [(current, 0)]
        visited: set[Path] = set()
        max_depth = 5
        while queue:
            directory, depth = queue.pop(0)
            if directory in visited:
                continue
            visited.add(directory)
            if depth > 0 and _has_sfdx_marker(directory):
                return directory
            if depth >= max_depth:
                continue
            try:
                for child in sorted(directory.iterdir()):
                    if not child.is_dir() or child.name.startswith("."):
                        continue
                    if child.name in _SKIP_SEARCH_DIRS:
                        continue
                    queue.append((child, depth + 1))
            except OSError:
                continue

    return current
