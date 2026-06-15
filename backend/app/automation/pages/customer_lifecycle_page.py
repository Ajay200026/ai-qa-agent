import logging
import re

from playwright.async_api import Locator

from app.automation.combobox import menu_option_candidates
from app.automation.pages.base_page import POLL_MS, BasePage
from app.automation.request_modules import normalize_request_module
from app.automation.scope import all_scopes, find_visible_in_scopes
from app.automation.workspace_tab import (
    find_data_change_page,
    focus_data_change_form,
    sales_office_field_present,
)

logger = logging.getLogger(__name__)

QUEUES_TAB_NAMES = [
    "Customer_Life_Cycle_Queues",
    "Customer Life Cycle Queues",
    "Customer Lifecycle Queues",
]


class CustomerLifecyclePage(BasePage):
    def _queues_tab_candidates(self) -> list[Locator]:
        page = self.page
        candidates: list[Locator] = []
        for name in QUEUES_TAB_NAMES:
            candidates.append(page.get_by_role("tab", name=name))
            candidates.append(page.get_by_text(name, exact=True))
        candidates.append(page.get_by_role("tab", name=re.compile(r"Customer.*Life.*Cycle.*Queues", re.I)))
        candidates.append(page.get_by_text(re.compile(r"Customer[_\s]*Life[_\s]*Cycle[_\s]*Queues", re.I)))
        return candidates

    def _new_button_candidates(self, button_label: str = "New") -> list[Locator]:
        page = self.page
        label = button_label.strip() or "New"
        candidates: list[Locator] = [
            page.get_by_role("button", name=re.compile(r"^NEW$", re.I)),
            page.get_by_role("button", name=label),
            page.locator(f'button[title="{label}"]'),
            page.get_by_role("button", name=re.compile(rf"^{re.escape(label)}$", re.I)),
        ]
        if label.lower() == "new":
            candidates.extend([
                page.locator('button[title="New"]'),
                page.locator(".slds-button").filter(has_text=re.compile(r"^New$", re.I)),
                page.get_by_text(re.compile(r"^NEW$", re.I)),
            ])
        return candidates

    def _new_menu_chevron_candidates(self) -> list[Locator]:
        """Split-button chevron on the red NEW control."""
        page = self.page
        new_group = page.locator("button, div, span").filter(
            has_text=re.compile(r"^NEW$", re.I)
        )
        return [
            new_group.locator(
                "svg, [class*='chevron'], [class*='arrow'], [class*='caret'], "
                "[class*='icon'], button:last-child, span:last-child"
            ),
            page.locator("button").filter(has_text=re.compile(r"NEW", re.I)).locator(
                "svg, [class*='chevron'], [class*='arrow']"
            ),
            page.locator("[class*='chevron'], [class*='caret']").filter(
                has=page.locator("button, div").filter(has_text=re.compile(r"NEW", re.I))
            ),
        ]

    async def _is_new_request_menu_open(self) -> bool:
        table = self.page.locator("table, .slds-table, [role='grid']")
        try:
            return await self.page.get_by_text("NEW DATA CHANGE", exact=True).filter(
                has_not=table
            ).first.is_visible(timeout=400)
        except Exception:
            return False

    async def _open_new_request_menu(self) -> None:
        if await self._is_new_request_menu_open():
            return

        for candidate in self._new_button_candidates("New"):
            try:
                btn = candidate.first
                if not await btn.is_visible(timeout=2000):
                    continue
                await btn.scroll_into_view_if_needed()
                await btn.click(timeout=3000)
                await self.cancellable_sleep(500)
                if await self._is_new_request_menu_open():
                    logger.info("NEW request menu opened via button click")
                    return
                # Split button — click chevron / right edge
                box = await btn.bounding_box()
                if box:
                    await self.page.mouse.click(
                        box["x"] + box["width"] - 8,
                        box["y"] + box["height"] / 2,
                    )
                    await self.cancellable_sleep(500)
                    if await self._is_new_request_menu_open():
                        logger.info("NEW request menu opened via chevron click")
                        return
            except Exception:
                continue

        for chevron in self._new_menu_chevron_candidates():
            try:
                if await chevron.first.is_visible(timeout=1000):
                    await chevron.first.click(timeout=2000)
                    await self.cancellable_sleep(500)
                    if await self._is_new_request_menu_open():
                        logger.info("NEW request menu opened via chevron locator")
                        return
            except Exception:
                continue

        await self.screenshot("new_menu_not_open")
        raise RuntimeError("NEW dropdown menu did not open after clicking the button")

    async def _find_menu_option(self, option: str) -> tuple[Locator, object] | None:
        def builder(scope):
            return menu_option_candidates(scope, option)

        return await find_visible_in_scopes(
            all_scopes(self.page),
            builder,
            per_locator_ms=600,
        )

    async def _click_menu_option(self, option: str) -> None:
        found = await self._find_menu_option(option)
        if not found:
            await self.screenshot("request_module_not_found")
            raise RuntimeError(
                f"Could not find request module '{option}' in the New menu. URL: {self.page.url}"
            )

        scope, locator = found
        target = locator.first
        await target.scroll_into_view_if_needed()
        pages_before = len(self.page.context.pages)
        new_page = None
        try:
            async with self.page.context.expect_page(timeout=8_000) as page_info:
                try:
                    await target.click(timeout=3_000)
                except Exception:
                    try:
                        await target.click(force=True, timeout=3_000)
                    except Exception:
                        await target.evaluate("el => el.click()")
            new_page = await page_info.value
            await new_page.wait_for_load_state("domcontentloaded", timeout=15_000)
            logger.info("Module opened new browser tab: %s", new_page.url)
        except Exception:
            try:
                await target.click(timeout=3_000)
            except Exception:
                try:
                    await target.click(force=True, timeout=3_000)
                except Exception:
                    await target.evaluate("el => el.click()")
            if len(self.page.context.pages) > pages_before:
                new_page = self.page.context.pages[-1]
                await new_page.wait_for_load_state("domcontentloaded", timeout=15_000)
                logger.info("Module opened browser tab (detected): %s", new_page.url)

        if new_page:
            await new_page.bring_to_front()
            self.page = new_page
        logger.info("Clicked menu option '%s' in scope %s", option, getattr(scope, "url", "page"))

    async def _wait_for_module_navigation(self, timeout: int = 45_000) -> None:
        """Wait for Data Change form + Sales Office field on any browser tab."""
        elapsed = 0
        while elapsed < timeout:
            self._check_cancelled()

            found = await find_data_change_page(self.page)
            if found:
                await found.bring_to_front()
                self.page = found

            page = self.page
            if await sales_office_field_present(page):
                logger.info("Sales Office field ready on %s", page.url)
                return

            page = await focus_data_change_form(page, activate=True)
            self.page = page
            if await sales_office_field_present(page):
                logger.info("Sales Office field ready on %s", page.url)
                return

            await self.cancellable_sleep(500)
            elapsed += 500

        await self.screenshot("data_change_tab_not_ready")
        raise TimeoutError("Data Change tab did not open after module selection")

    async def select_request_module(self, module_option: str) -> None:
        """Select a request type from the New (+) menu (not a form dropdown)."""
        label = normalize_request_module(module_option)
        await self.open_queues_object()
        await self._open_new_request_menu()
        await self._click_menu_option(label)
        await self.cancellable_sleep(1000)
        await self._wait_for_module_navigation()
        logger.info("Selected request module: %s", label)

    async def open_queues_object(self) -> None:
        await self.wait_for_queues_ready()
        await self.ensure_queues_tab_selected()
        logger.info("Customer Life Cycle Queue object is open")

    async def is_on_queues_page(self) -> bool:
        for candidate in self._new_button_candidates():
            try:
                if await candidate.first.is_visible():
                    return True
            except Exception:
                continue
        for candidate in self._queues_tab_candidates():
            try:
                if await candidate.first.is_visible():
                    return True
            except Exception:
                continue
        return False

    async def wait_for_queues_ready(self, timeout: int = 90_000) -> None:
        elapsed = 0
        while elapsed < timeout:
            self._check_cancelled()
            if await self.is_on_queues_page():
                await self.cancellable_sleep(1500)
                logger.info("Customer Life Cycle Queues page ready — URL: %s", self.page.url)
                return
            await self.cancellable_sleep(POLL_MS)
            elapsed += POLL_MS

        await self.screenshot("queues_page_timeout")
        raise TimeoutError(
            f"Customer Life Cycle Queues page not ready within {timeout}ms. URL: {self.page.url}"
        )

    async def ensure_queues_tab_selected(self) -> None:
        if await self.is_on_queues_page():
            for candidate in self._new_button_candidates():
                try:
                    if await candidate.first.is_visible():
                        return
                except Exception:
                    continue

        for candidate in self._queues_tab_candidates():
            try:
                await self.click_locator(candidate, timeout=8_000)
                await self.cancellable_sleep(1500)
                return
            except Exception:
                continue

        await self.wait_for_queues_ready()

    async def click_new_button(self, button_label: str = "New") -> None:
        await self.open_queues_object()
        await self._open_new_request_menu()
        logger.info("Clicked '%s' button — menu open", button_label)

    async def create_data_change_request(
        self,
        *,
        button_label: str = "New",
        menu_option: str = "NEW DATA CHANGE",
    ) -> None:
        await self.open_queues_object()

        last_error: Exception | None = None
        for candidate in self._new_button_candidates(button_label):
            try:
                await self.click_locator(candidate, timeout=15_000)
                await self.cancellable_sleep(800)
                logger.info("Clicked '%s' button", button_label)
                break
            except Exception as exc:
                last_error = exc
        else:
            raise RuntimeError(
                f"Could not find '{button_label}' button on Queues page"
            ) from last_error

        await self.select_request_module(menu_option)

    async def click_new_request(self) -> None:
        await self.create_data_change_request()
