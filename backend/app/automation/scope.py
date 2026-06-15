"""Page + iframe scope helpers for Salesforce Visualforce / Lightning forms."""

from collections.abc import Callable
from typing import TypeAlias

from playwright.async_api import Frame, Locator, Page

PageOrFrame: TypeAlias = Page | Frame


def child_frames(page: Page) -> list[Frame]:
    return [f for f in page.frames if f != page.main_frame and f.url and "about:blank" not in f.url]


def all_scopes(page: Page) -> list[PageOrFrame]:
    return [page, *child_frames(page)]


def frame_urls(page: Page) -> list[str]:
    return [f.url for f in page.frames if f.url]


async def find_visible_in_scopes(
    scopes: list[PageOrFrame],
    build_locators: Callable[[PageOrFrame], list[Locator]],
    *,
    per_locator_ms: int = 400,
) -> tuple[PageOrFrame, Locator] | None:
    for scope in scopes:
        for locator in build_locators(scope):
            try:
                if await locator.first.is_visible(timeout=per_locator_ms):
                    return scope, locator
            except Exception:
                continue
    return None
