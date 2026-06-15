import logging
import re

from playwright.async_api import Locator

from app.automation.combobox import PLACEHOLDER_PATTERNS
from app.automation.field_resolver import FieldActions, SmartFieldResolver
from app.automation.form_field import (
    click_lookup,
    click_picklist,
    click_search_button,
    customer_lookup_visible,
    field_present,
    find_input,
    resolve_form_scope,
    type_in_input,
)
from app.automation.pages.base_page import BasePage
from app.automation.scope import PageOrFrame
from app.automation.workspace_tab import focus_data_change_form

logger = logging.getLogger(__name__)

FORM_FIELD_LABELS = ("Sales Office", "Customer Number", "Customer Name/Number")


class DataChangePage(BasePage):
    def __init__(
        self,
        page,
        artifacts_dir=None,
        execution_id=None,
        template_key: str = "DATA_CHANGE_REQUEST",
        db=None,
    ):
        super().__init__(page, artifacts_dir, execution_id)
        self.template_key = template_key
        resolver = SmartFieldResolver(page, template_key, db)
        self.field_actions = FieldActions(page, resolver, self._check_cancelled)

    async def focus_form(self) -> None:
        """Switch to the Data Change workspace tab / page where form fields live."""
        self.page = await focus_data_change_form(self.page)

    async def wait_for_request_form(self, timeout: int = 10_000) -> None:
        """Wait for Sales Office field on the active Data Change tab."""
        elapsed = 0
        while elapsed < timeout:
            self._check_cancelled()
            scope = await resolve_form_scope(self.page, "Sales Office")
            self.page = await self._scope_owner(scope)
            if await field_present(scope, "Sales Office"):
                logger.info("Request form ready — 'Sales Office' field found")
                self._form_scope = scope
                return
            await self.focus_form()
            await self.cancellable_sleep(400)
            elapsed += 400
        await self.screenshot("request_form_not_ready")
        raise TimeoutError(
            "Data Change form not found — check the '* New Data Change' tab is open"
        )

    @staticmethod
    async def _scope_owner(scope) -> object:
        from playwright.async_api import Frame, Page

        return scope if isinstance(scope, Page) else scope.page

    async def select_sales_office(self, office: str | None = None) -> str:
        await self.wait_for_request_form(timeout=10_000)
        scope = getattr(self, "_form_scope", None) or await resolve_form_scope(
            self.page, "Sales Office"
        )
        self.page = await self._scope_owner(scope)
        await self.screenshot("before_sales_office")
        try:
            selected = await click_picklist(scope, "Sales Office", office)
        except RuntimeError:
            await self.screenshot("sales_office_failed")
            raise
        logger.info("Selected sales office: %s", selected)
        return selected

    async def _ensure_form_scope(self, field_key: str = "Customer Number"):
        scope = getattr(self, "_form_scope", None)
        if scope and await field_present(scope, field_key):
            return scope
        scope = await resolve_form_scope(self.page, field_key)
        self._form_scope = scope
        self.page = await self._scope_owner(scope)
        return scope

    async def open_customer_search(self) -> None:
        scope = await self._ensure_form_scope("Customer Number")
        inp = await find_input(scope, "Customer Number")
        await inp.click(timeout=5000)
        logger.info("Opened customer search input")

    async def enter_customer_number(self, customer_number: str) -> None:
        scope = await self._ensure_form_scope("Customer Number")
        self._last_customer_number = customer_number
        await type_in_input(scope, "Customer Number", customer_number)

    async def select_first_customer_from_dropdown(self) -> None:
        scope = await self._ensure_form_scope("Customer Number")
        query = getattr(self, "_last_customer_number", "__any__")
        await click_lookup(scope, "Customer Number", query)
        logger.info("Selected first customer from dropdown")

    async def search_and_select_customer(self, customer_query: str) -> None:
        scope = await self._ensure_form_scope("Customer Number")
        await click_lookup(scope, "Customer Number", customer_query)

    async def open_customer_details_tab(self) -> None:
        def builder(scope: PageOrFrame) -> list[Locator]:
            return [
                scope.get_by_role("tab", name="Customer Details"),
                scope.get_by_text("Customer Details", exact=True),
            ]

        found = await self.find_in_any_scope(builder)
        if found:
            _, candidate = found
            await self.click_locator(candidate, timeout=15_000)
            logger.info("Opened Customer Details tab")
            return

        for candidate in [
            self.resolve_locator("data_change.customer_details_tab"),
            self.page.get_by_role("tab", name="Customer Details"),
        ]:
            try:
                await self.click_locator(candidate, timeout=15_000)
                logger.info("Opened Customer Details tab")
                return
            except Exception:
                continue
        raise RuntimeError("Could not open Customer Details tab")

    async def modify_primary_group(self, value: str) -> None:
        scope = await self._ensure_form_scope("Primary Group")
        await self.open_customer_details_tab()
        scope = await resolve_form_scope(self.page, "Primary Group")
        self._form_scope = scope
        self.page = await self._scope_owner(scope)
        selected = await click_picklist(scope, "Primary Group", value)
        logger.info("Modified Primary Group to: %s", selected)

    async def submit(self) -> None:
        scope = await self._ensure_form_scope("Primary Group")
        if not await field_present(scope, "Primary Group"):
            scope = await self._ensure_form_scope("Customer Number")
        from app.automation.form_field import click_form_button

        await click_form_button(scope, "Submit")
        await self.cancellable_sleep(2000)
        logger.info("Clicked Submit")

    async def select_module(self, module: str) -> None:
        locator = self.resolve_locator("data_change.module_selection")
        await locator.select_option(label=module)
        logger.info("Selected module: %s", module)

    async def wait_for_customer_dropdown(self, timeout: int = 20_000) -> None:
        scope = await self._ensure_form_scope("Customer Number")
        # Do NOT press Escape here — it closes the customer lookup dropdown.
        elapsed = 0
        while elapsed < timeout:
            self._check_cancelled()
            if await customer_lookup_visible(scope, "Customer Number"):
                logger.info("Customer search dropdown is visible")
                return
            await self.cancellable_sleep(400)
            elapsed += 400
        await self.screenshot("customer_dropdown_not_visible")
        raise TimeoutError("Customer search dropdown did not appear")

    async def wait_for_data(self, timeout: int = 30_000) -> None:
        elapsed = 0
        while elapsed < timeout:
            self._check_cancelled()
            for scope in self.get_all_scopes():
                if await field_present(scope, "Primary Group"):
                    logger.info("Customer data loaded — Primary Group field visible")
                    return
                for label in ("Customer Details", "Primary Group", "Request Information"):
                    try:
                        section = scope.get_by_text(label, exact=False).first
                        if await section.is_visible(timeout=400):
                            logger.info("Customer data loaded — '%s' section visible", label)
                            return
                    except Exception:
                        pass
                tab = scope.get_by_role("tab", name=re.compile(r"customer\s+details", re.I))
                try:
                    if await tab.first.is_visible(timeout=400):
                        logger.info("Customer data loaded — Customer Details tab visible")
                        return
                except Exception:
                    pass
            await self.cancellable_sleep(500)
            elapsed += 500
        await self.screenshot("customer_data_not_loaded")
        raise TimeoutError(
            "Customer data did not load — select customer from dropdown, then Search or wait for sections"
        )

    async def search(self) -> None:
        from app.automation.form_field import _customer_selected, dismiss_global_search

        scope = await self._ensure_form_scope("Customer Number")
        await dismiss_global_search(scope)
        await self.screenshot("before_search")

        customer_number = getattr(self, "_last_customer_number", "060")
        if not await _customer_selected(scope, "Customer Number", customer_number):
            raise RuntimeError(
                "Customer not selected — pick a row from the dropdown "
                "(e.g. '0500931141 - ZETT BUILDING MAINTENANCE') before Search"
            )

        clicked = await click_search_button(scope, "Customer Number")
        if not clicked:
            logger.info("No form Search button — waiting for customer data after lookup selection")
        await self.wait_for_data()
        logger.info("Search completed")

    async def save_draft(self) -> None:
        await self.safe_click("data_change.save_draft")
        await self.cancellable_sleep(2000)
        logger.info("Save Draft clicked")

    async def has_success_message(self) -> bool:
        for locator_name in ("data_change.submit_success", "data_change.success_toast"):
            try:
                toast = self.resolve_locator(locator_name)
                if await toast.is_visible():
                    return True
            except Exception:
                continue
        text = await self.get_toast_text()
        return text is not None and any(k in text.lower() for k in ("success", "submitted", "saved"))
