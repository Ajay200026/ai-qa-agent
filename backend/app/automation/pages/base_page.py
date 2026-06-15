import logging
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from collections.abc import Callable

from playwright.async_api import Locator, Page, expect

from app.automation.locators import LocatorDef, LocatorStrategy, get_locator
from app.automation.scope import PageOrFrame, all_scopes, find_visible_in_scopes, frame_urls
from app.core.config import get_settings
from app.services.execution_registry import execution_registry

logger = logging.getLogger(__name__)

POLL_MS = 2_000


class BasePage:
    def __init__(
        self,
        page: Page,
        artifacts_dir: Path | None = None,
        execution_id: UUID | None = None,
    ):
        self.page = page
        self.artifacts_dir = artifacts_dir
        self.execution_id = execution_id
        self.settings = get_settings()

    def _check_cancelled(self) -> None:
        execution_registry.check_cancelled(self.execution_id)

    async def cancellable_sleep(self, ms: int) -> None:
        remaining = ms
        while remaining > 0:
            self._check_cancelled()
            chunk = min(500, remaining)
            await self.page.wait_for_timeout(chunk)
            remaining -= chunk

    async def wait_locator_visible(self, locator: Locator, timeout: int = 20_000) -> None:
        elapsed = 0
        last_error: Exception | None = None
        while elapsed < timeout:
            self._check_cancelled()
            try:
                await locator.first.wait_for(
                    state="visible",
                    timeout=min(POLL_MS, timeout - elapsed),
                )
                return
            except Exception as exc:
                last_error = exc
                elapsed += POLL_MS
        raise TimeoutError(f"Element not visible within {timeout}ms") from last_error

    async def click_locator(self, locator: Locator, timeout: int = 20_000) -> None:
        await self.wait_locator_visible(locator, timeout=timeout)
        self._check_cancelled()
        target = locator.first
        await target.scroll_into_view_if_needed()
        try:
            await target.click(timeout=5_000)
        except Exception:
            await target.click(force=True, timeout=5_000)

    async def click_locator_fast(self, locator: Locator, timeout: int = 4_000) -> None:
        """Click with a short timeout — for menus already open on screen."""
        await self.wait_locator_visible(locator, timeout=timeout)
        self._check_cancelled()
        target = locator.first
        await target.scroll_into_view_if_needed()
        try:
            await target.click(timeout=2_000)
        except Exception:
            try:
                await target.click(force=True, timeout=2_000)
            except Exception:
                await target.evaluate("el => el.click()")

    def resolve_locator(self, locator_name: str) -> Locator:
        loc_def = get_locator(locator_name)
        return self._build_locator(loc_def)

    def _build_locator(self, loc_def: LocatorDef) -> Locator:
        match loc_def.strategy:
            case LocatorStrategy.ROLE:
                return self.page.get_by_role(loc_def.role or "button", name=loc_def.value)
            case LocatorStrategy.LABEL:
                return self.page.get_by_label(loc_def.value, exact=loc_def.exact)
            case LocatorStrategy.PLACEHOLDER:
                return self.page.get_by_placeholder(loc_def.value, exact=loc_def.exact)
            case LocatorStrategy.TEXT:
                return self.page.get_by_text(loc_def.value, exact=loc_def.exact)
            case LocatorStrategy.TEST_ID:
                return self.page.get_by_test_id(loc_def.value)
            case _:
                raise ValueError(f"Unsupported locator strategy: {loc_def.strategy}")

    async def safe_click(self, locator_name: str, *, retries: int = 3) -> None:
        locator = self.resolve_locator(locator_name)
        last_error: Exception | None = None
        for attempt in range(retries):
            self._check_cancelled()
            try:
                await self.wait_locator_visible(locator, timeout=15_000)
                await locator.click()
                return
            except Exception as exc:
                last_error = exc
                logger.warning("Click attempt %d failed for %s: %s", attempt + 1, locator_name, exc)
                await self.cancellable_sleep(500)
        raise RuntimeError(f"Failed to click '{locator_name}' after {retries} attempts") from last_error

    async def safe_fill(self, locator_name: str, value: str, *, retries: int = 3) -> None:
        locator = self.resolve_locator(locator_name)
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                await locator.wait_for(state="visible", timeout=10000)
                await locator.clear()
                await locator.fill(value)
                return
            except Exception as exc:
                last_error = exc
                logger.warning("Fill attempt %d failed for %s: %s", attempt + 1, locator_name, exc)
                await self.page.wait_for_timeout(500)
        raise RuntimeError(f"Failed to fill '{locator_name}' after {retries} attempts") from last_error

    async def wait_for_visible(self, locator_name: str, timeout: int | None = None) -> None:
        locator = self.resolve_locator(locator_name)
        await locator.wait_for(state="visible", timeout=timeout or self.settings.playwright_timeout_ms)

    async def wait_for_hidden(self, locator_name: str, timeout: int | None = None) -> None:
        locator = self.resolve_locator(locator_name)
        await locator.wait_for(state="hidden", timeout=timeout or self.settings.playwright_timeout_ms)

    def _launcher_menu(self) -> Locator:
        return self.page.locator("one-app-launcher-menu, .oneAppLauncherMenu").first

    async def wait_for_lightning_ready(self, timeout: int = 60000) -> None:
        """Wait for Salesforce Lightning shell after login — not for a specific app."""
        chunk = max(timeout // 4, 10000)
        checks = [
            lambda: self.page.locator(".oneHeader"),
            lambda: self.page.locator("#oneHeader"),
            lambda: self.page.locator(".slds-global-header"),
            lambda: self.page.locator("one-app-nav-bar"),
            lambda: self.page.get_by_role("button", name="App Launcher"),
        ]

        last_url = self.page.url
        for locator_fn in checks:
            try:
                await self.wait_locator_visible(locator_fn(), timeout=chunk)
                await self.cancellable_sleep(1500)
                return
            except Exception:
                continue

        if re.search(r"lightning\.force\.com|\.salesforce\.com", self.page.url):
            await self.cancellable_sleep(3000)
            return

        raise TimeoutError(
            f"Salesforce Lightning UI not ready within {timeout}ms. Last URL: {last_url}"
        )

    async def wait_for_app_ready(self, app_name: str, timeout: int = 60000) -> None:
        """Wait until a named app has loaded — do not treat the App Launcher button as success."""
        app_name_lower = app_name.lower()
        app_checks: dict[str, list] = {
            "onboarding": [
                lambda: self.page.get_by_role("tab", name="Customer_Life_Cycle_Queues"),
                lambda: self.page.get_by_role("button", name="New"),
                lambda: self.page.get_by_role("tab", name="Customer Lifecycle"),
                lambda: self.page.locator(".slds-tabs_default"),
            ],
        }
        checks = app_checks.get(app_name_lower, [])
        if not checks:
            await self.page.wait_for_load_state("domcontentloaded")
            await self.page.wait_for_timeout(2000)
            return

        chunk = max(timeout // len(checks), POLL_MS)
        for locator_fn in checks:
            try:
                await self.wait_locator_visible(locator_fn(), timeout=chunk)
                await self.cancellable_sleep(1500)
                return
            except Exception:
                continue

        raise TimeoutError(
            f"App '{app_name}' did not load within {timeout}ms. URL: {self.page.url}"
        )

    async def wait_for_network_idle(self) -> None:
        """Prefer wait_for_lightning_ready for Salesforce pages."""
        try:
            await self.wait_for_lightning_ready(timeout=self.settings.playwright_timeout_ms)
        except Exception:
            await self.page.wait_for_load_state("load")

    async def screenshot(self, name: str) -> str | None:
        if not self.artifacts_dir:
            return None
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        path = self.artifacts_dir / f"{name}.png"
        await self.page.screenshot(path=str(path), full_page=True)
        return str(path)

    async def get_toast_text(self) -> str | None:
        try:
            toast = self.resolve_locator("generic.toast_message")
            if await toast.is_visible():
                return await toast.text_content()
        except Exception:
            pass
        return None

    async def assert_visible(self, locator_name: str) -> None:
        locator = self.resolve_locator(locator_name)
        await expect(locator).to_be_visible()

    def get_all_scopes(self) -> list[PageOrFrame]:
        return all_scopes(self.page)

    def get_frame_urls(self) -> list[str]:
        return frame_urls(self.page)

    async def find_in_any_scope(
        self,
        build_locators: Callable[[PageOrFrame], list[Locator]],
        *,
        per_locator_ms: int = 400,
    ) -> tuple[PageOrFrame, Locator] | None:
        return await find_visible_in_scopes(
            self.get_all_scopes(),
            build_locators,
            per_locator_ms=per_locator_ms,
        )

    async def wait_for_condition(
        self,
        check_fn: Callable[[], bool],
        timeout: int = 15_000,
    ) -> None:
        elapsed = 0
        while elapsed < timeout:
            self._check_cancelled()
            if check_fn():
                return
            await self.cancellable_sleep(250)
            elapsed += 250
        raise TimeoutError(f"Condition not met within {timeout}ms")
