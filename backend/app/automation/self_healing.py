"""Per-step retry with backoff and locator healing."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

TRANSIENT_PATTERNS = (
    "timeout",
    "not visible",
    "not found",
    "detached",
    "intercept",
    "stale",
    "waiting for",
)


def is_transient_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(p in msg for p in TRANSIENT_PATTERNS)


async def retry_with_heal(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay_ms: int = 500,
    heal_fn: Callable[[], Awaitable[None]] | None = None,
) -> T:
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await fn()
        except Exception as exc:
            last_exc = exc
            if attempt >= max_attempts - 1 or not is_transient_error(exc):
                raise
            logger.info("Transient failure (attempt %d/%d): %s", attempt + 1, max_attempts, exc)
            if heal_fn:
                try:
                    await heal_fn()
                except Exception as heal_exc:
                    logger.debug("Heal step failed: %s", heal_exc)
            await asyncio.sleep((base_delay_ms * (attempt + 1)) / 1000)
    raise last_exc or RuntimeError("retry_with_heal failed")
