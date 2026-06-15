import logging
import re

from playwright.async_api import Locator

from app.automation.pages.base_page import POLL_MS, BasePage
from app.automation.salesforce_utils import normalize_app_name

logger = logging.getLogger(__name__)

SLOW_ORG_TIMEOUT_MS = 90_000


class AppLauncherPage(BasePage):
    def _launcher_button_candidates(self) -> list[Locator]:
        page = self.page
        return [
            page.locator(".slds-icon-waffle_container"),
            page.locator("button.slds-icon-waffle_container"),
            page.locator('button[title="App Launcher"]'),
            page.get_by_role("button", name="App Launcher"),
            page.get_by_role("button", name=re.compile(r"App Launcher", re.I)),
        ]

    def _search_input_candidates(self) -> list[Locator]:
        page = self.page
        return [
            page.get_by_placeholder("Search apps and items..."),
            page.get_by_placeholder(re.compile(r"Search apps", re.I)),
            page.locator('one-app-launcher-menu input[type="search"]'),
            page.locator("one-app-launcher-menu input"),
            page.locator('.oneAppLauncherMenu input[type="search"]'),
        ]

    async def _is_launcher_open(self) -> bool:
        for candidate in self._search_input_candidates():
            try:
                if await candidate.first.is_visible():
                    return True
            except Exception:
                continue
        return False

    async def _click_launcher_button(self, timeout: int = SLOW_ORG_TIMEOUT_MS) -> None:
        await self.wait_for_lightning_ready(timeout=timeout)
        elapsed = 0
        last_error: Exception | None = None

        while elapsed < timeout:
            self._check_cancelled()
            for candidate in self._launcher_button_candidates():
                try:
                    await self.click_locator(candidate, timeout=POLL_MS)
                    return
                except Exception as exc:
                    last_error = exc
            await self.cancellable_sleep(POLL_MS)
            elapsed += POLL_MS

        await self.screenshot("app_launcher_button_timeout")
        raise RuntimeError(
            f"Could not click App Launcher within {timeout}ms. URL: {self.page.url}"
        ) from last_error

    async def _wait_for_launcher_search(self, timeout: int = SLOW_ORG_TIMEOUT_MS) -> Locator:
        elapsed = 0
        while elapsed < timeout:
            self._check_cancelled()
            for candidate in self._search_input_candidates():
                try:
                    await self.wait_locator_visible(candidate, timeout=POLL_MS)
                    return candidate.first
                except Exception:
                    continue
            await self.cancellable_sleep(POLL_MS)
            elapsed += POLL_MS

        await self.screenshot("app_launcher_search_timeout")
        raise TimeoutError(
            f"App Launcher search box not visible within {timeout}ms. URL: {self.page.url}"
        )

    async def open(self) -> None:
        if await self._is_launcher_open():
            logger.info("App Launcher already open")
            return
        await self._click_launcher_button()
        await self._wait_for_launcher_search()
        logger.info("App Launcher opened")

    async def _click_app_in_launcher(self, app_name: str) -> None:
        app_name = normalize_app_name(app_name)
        menu = self._launcher_menu()
        await self.wait_locator_visible(menu, timeout=15_000)

        candidates = [
            menu.get_by_role("link", name=app_name, exact=True),
            menu.get_by_role("option", name=app_name, exact=True),
            menu.locator(f'a[data-label="{app_name}"]'),
            menu.get_by_text(app_name, exact=True),
        ]
        for locator in candidates:
            try:
                await self.click_locator(locator, timeout=8_000)
                return
            except Exception:
                continue
        await self.screenshot("app_launcher_app_not_found")
        raise RuntimeError(
            f"Could not find '{app_name}' in App Launcher results. URL: {self.page.url}"
        )

    async def search_and_open_app(self, app_name: str = "Onboarding") -> None:
        app_name = normalize_app_name(app_name)
        await self.open()
        search = await self._wait_for_launcher_search()
        await search.clear()
        await search.fill(app_name)
        await self.cancellable_sleep(1000)
        await self._click_app_in_launcher(app_name)

        try:
            await self._launcher_menu().wait_for(state="hidden", timeout=5_000)
        except Exception:
            logger.debug("App Launcher menu did not close — app may still be loading")

        await self.wait_for_app_ready(app_name, timeout=SLOW_ORG_TIMEOUT_MS)
        logger.info("Opened app: %s", app_name)
