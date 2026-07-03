"""Resolve a valid Playwright browsers directory across local dev, Cursor, and Docker."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_INVALID_PATH_MARKERS = ("cursor-sandbox-cache", "/tmp/cursor-")


def _has_chromium_install(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any(path.glob("chromium-*"))


def _is_unusable_path(path: str | None) -> bool:
    if not path:
        return True
    lowered = path.lower()
    if any(marker in lowered for marker in _INVALID_PATH_MARKERS):
        return True
    candidate = Path(path)
    if not candidate.is_dir():
        return True
    return not _has_chromium_install(candidate)


def _default_browser_paths() -> list[Path]:
    paths: list[Path] = []
    if sys.platform == "darwin":
        paths.append(Path.home() / "Library/Caches/ms-playwright")
    elif sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            paths.append(Path(local_app_data) / "ms-playwright")
    else:
        paths.append(Path.home() / ".cache/ms-playwright")
    # Official Playwright Docker images ship browsers here.
    paths.append(Path("/ms-playwright"))
    return paths


def resolve_playwright_browsers_path(configured: str | None = None) -> str | None:
    """Pick the first browsers directory that actually contains Chromium."""
    candidates: list[str] = []
    for value in (configured, os.environ.get("PLAYWRIGHT_BROWSERS_PATH")):
        if value and value not in candidates:
            candidates.append(value)

    for default in _default_browser_paths():
        value = str(default)
        if value not in candidates:
            candidates.append(value)

    for candidate in candidates:
        if _is_unusable_path(candidate):
            continue
        if configured and candidate != configured:
            logger.warning(
                "Ignoring invalid PLAYWRIGHT_BROWSERS_PATH=%r; using %r",
                configured,
                candidate,
            )
        return candidate

    return configured


def ensure_playwright_browsers_path(configured: str | None = None) -> str | None:
    """Set PLAYWRIGHT_BROWSERS_PATH in the process environment when resolvable."""
    resolved = resolve_playwright_browsers_path(configured)
    if resolved:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = resolved
    return resolved
