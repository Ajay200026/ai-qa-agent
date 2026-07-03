"""Per-test-case identity resolution.

Priority order:
1. Explicit `IdentityMap` entry for (tc_bottler, tc_role)
   - if `enabled=False`, return `None` (skip impersonation).
   - if `override_*` set, apply overrides.
2. Raw `(tc_bottler, tc_role)` from the test case if both are non-empty.
3. Scenario-level `default` (`LoginAsTarget`) if enabled.
4. `None` (no impersonation, stay as the admin login).
"""

from __future__ import annotations

import logging
from typing import Mapping

from app.schemas.login_as import IdentityMap, IdentityMapEntry, LoginAsTarget

logger = logging.getLogger(__name__)


def _coerce_identity_map(value: Mapping | IdentityMap | None) -> IdentityMap | None:
    if value is None:
        return None
    if isinstance(value, IdentityMap):
        return value
    try:
        return IdentityMap.model_validate(value)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Ignoring invalid identity_map: %s", exc)
        return None


def _coerce_default(value: Mapping | LoginAsTarget | None) -> LoginAsTarget | None:
    if value is None:
        return None
    if isinstance(value, LoginAsTarget):
        return value
    try:
        return LoginAsTarget.model_validate(value)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Ignoring invalid login_as_target: %s", exc)
        return None


def resolve_identity(
    *,
    tc_bottler: str | None,
    tc_role: str | None,
    identity_map: Mapping | IdentityMap | None = None,
    default: Mapping | LoginAsTarget | None = None,
) -> LoginAsTarget | None:
    """Return the LoginAsTarget to impersonate for a single test case."""
    imap = _coerce_identity_map(identity_map)
    if imap is not None:
        entry: IdentityMapEntry | None = imap.find(tc_bottler, tc_role)
        if entry is not None:
            if not entry.enabled:
                logger.info(
                    "identity_selector.disabled bottler=%s role=%s",
                    tc_bottler,
                    tc_role,
                )
                return None
            bottler, role = entry.effective()
            return LoginAsTarget(
                bottler_id=bottler, onboarding_role=role, enabled=True
            )

    if tc_bottler and tc_role:
        return LoginAsTarget(
            bottler_id=tc_bottler.strip(),
            onboarding_role=tc_role.strip(),
            enabled=True,
        )

    fallback = _coerce_default(default)
    if fallback and fallback.enabled and fallback.bottler_id and fallback.onboarding_role:
        return fallback.normalized()

    return None
