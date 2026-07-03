import logging
import re

from playwright.async_api import Locator, Page

from app.automation.combobox import PLACEHOLDER_PATTERNS, is_auto_pick
from app.automation.field_resolver import FieldActions, SmartFieldResolver
from app.automation.form_field import (
    _customer_selected,
    click_lookup,
    click_picklist,
    click_search_button,
    customer_lookup_visible,
    field_present,
    find_input,
    resolve_form_scope,
    search_primary_group,
    type_in_input,
)
from app.automation.field_state import get_field_value
from app.automation.pages.base_page import BasePage
from app.automation.scope import PageOrFrame
from app.automation.workspace_tab import focus_data_change_form
from app.knowledge.data_change_field_registry import default_customer_search_query
from app.knowledge.sales_office_rules import resolve_bottler_id
from app.services.salesforce_query import (
    SoqlAuthError,
    SoqlClient,
    SoqlError,
    SoqlExecutionError,
)

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
        org=None,
        credentials=None,
    ):
        super().__init__(page, artifacts_dir, execution_id)
        self.template_key = template_key
        self.db = db
        self.org = org
        self.credentials = credentials or {}
        resolver = SmartFieldResolver(page, template_key, db)
        self.field_actions = FieldActions(page, resolver, self._check_cancelled)
        self._pinned_form_page: Page | None = None

    async def focus_form(self) -> None:
        """Switch to the Data Change workspace tab / page where form fields live."""
        from app.automation.workspace_tab import _form_visible

        if self._pinned_form_page and not self._pinned_form_page.is_closed():
            if self.page is not self._pinned_form_page:
                await self._pinned_form_page.bring_to_front()
            self.page = self._pinned_form_page
            if await _form_visible(self.page):
                return

        self.page = await focus_data_change_form(self.page)
        if await _form_visible(self.page):
            self._pinned_form_page = self.page

    async def _ensure_on_form_page(self) -> None:
        """Stay on the pinned Data Change browser tab — avoid re-scanning all tabs."""
        from app.automation.workspace_tab import _form_visible

        if self._pinned_form_page and not self._pinned_form_page.is_closed():
            if self.page is not self._pinned_form_page:
                await self._pinned_form_page.bring_to_front()
            self.page = self._pinned_form_page
            return
        await self.focus_form()
        if await _form_visible(self.page):
            self._pinned_form_page = self.page

    async def _primary_group_populated(self) -> bool:
        try:
            scope = await resolve_form_scope(
                self.page, "Primary Group", prefer_page=self._pinned_form_page
            )
            if not await field_present(scope, "Primary Group"):
                return False
            value = (await get_field_value(self.page, "Primary Group", self.db) or "").strip()
            if len(value) < 3:
                return False
            return not re.search(r"select|search", value, re.I)
        except Exception:
            return False

    async def _customer_field_confirmed(self, customer_number: str | None = None) -> bool:
        try:
            scope = await resolve_form_scope(
                self.page, "Customer Number", prefer_page=self._pinned_form_page
            )
            typed = customer_number or getattr(self, "_last_customer_number", "") or ""
            return await _customer_selected(scope, "Customer Number", typed)
        except Exception:
            return False

    async def customer_details_ready(self) -> bool:
        """True when customer is selected and Primary Group has loaded data."""
        await self._ensure_on_form_page()
        return await self._customer_field_confirmed() and await self._primary_group_populated()

    async def is_customer_loaded(self, customer_number: str | None = None) -> bool:
        """True when lookup shows NUMBER - NAME and Primary Group is populated."""
        await self._ensure_on_form_page()
        if not await self._customer_field_confirmed(customer_number):
            return False
        return await self._primary_group_populated()

    async def wait_for_request_form(self, timeout: int = 10_000) -> None:
        """Wait for Sales Office field on the active Data Change tab."""
        elapsed = 0
        while elapsed < timeout:
            self._check_cancelled()
            scope = await resolve_form_scope(
                self.page, "Sales Office", prefer_page=self._pinned_form_page
            )
            self.page = await self._scope_owner(scope)
            if await field_present(scope, "Sales Office"):
                logger.info("Request form ready — 'Sales Office' field found")
                self._form_scope = scope
                return
            await self._ensure_on_form_page()
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

    async def select_sales_office(
        self, office: str | None = None, *, bottler_id: str | None = None
    ) -> str:
        await self.wait_for_request_form(timeout=10_000)
        scope = getattr(self, "_form_scope", None) or await resolve_form_scope(
            self.page, "Sales Office", prefer_page=self._pinned_form_page
        )
        self.page = await self._scope_owner(scope)
        resolved_bottler = resolve_bottler_id(
            bottler_id=bottler_id,
            org=self.org,
            customer_target=None,
        )
        await self.screenshot("before_sales_office")
        try:
            selected = await click_picklist(
                scope, "Sales Office", office, bottler_id=resolved_bottler
            )
        except RuntimeError:
            await self.screenshot("sales_office_failed")
            raise
        logger.info("Selected sales office: %s", selected)
        return selected

    async def _ensure_form_scope(self, field_key: str = "Customer Number"):
        scope = getattr(self, "_form_scope", None)
        if scope and await field_present(scope, field_key):
            return scope
        if self._pinned_form_page and not self._pinned_form_page.is_closed():
            self.page = self._pinned_form_page
        scope = await resolve_form_scope(
            self.page, field_key, prefer_page=self._pinned_form_page
        )
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

    async def open_form_tab(self, tab_name: str) -> None:
        """Click a Data Change section tab (Customer Details, Account Receivable, etc.)."""
        await self._ensure_on_form_page()
        tab_pattern = re.compile(re.escape(tab_name), re.I)

        def builder(scope: PageOrFrame) -> list[Locator]:
            return [
                scope.get_by_role("tab", name=tab_pattern),
                scope.get_by_text(tab_name, exact=True),
            ]

        found = await self.find_in_any_scope(builder)
        if found:
            _scope, candidate = found
            try:
                if await candidate.get_attribute("aria-selected") == "true":
                    logger.info("Tab already active: %s", tab_name)
                    return
            except Exception:
                pass
            await self.click_locator(candidate, timeout=15_000)
            logger.info("Opened form tab: %s", tab_name)
            await self.cancellable_sleep(500)
            return

        try:
            await self.click_locator(
                self.page.get_by_role("tab", name=tab_pattern), timeout=15_000
            )
            logger.info("Opened form tab: %s", tab_name)
            await self.cancellable_sleep(500)
            return
        except Exception as exc:
            raise RuntimeError(f"Could not open form tab '{tab_name}'") from exc

    async def open_customer_details_tab(self) -> None:
        await self._ensure_on_form_page()
        if await self.customer_details_ready():
            logger.info("Customer Details already active with loaded data")
            return
        await self.open_form_tab("Customer Details")
        if await self.customer_details_ready():
            return
        raise RuntimeError("Could not open Customer Details tab")

    async def modify_primary_group(self, value: str) -> None:
        await self._ensure_on_form_page()
        if not await self.is_customer_loaded():
            await self.wait_for_data()
        await self.open_customer_details_tab()
        scope = await resolve_form_scope(
            self.page, "Primary Group", prefer_page=self._pinned_form_page
        )
        self._form_scope = scope
        self.page = await self._scope_owner(scope)

        from app.automation.form_field import search_primary_group

        result = await search_primary_group(scope, value)
        if not is_auto_pick(value) and value.upper() not in result.upper():
            raise RuntimeError(
                f"Primary Group search '{value}' did not stick — field shows {result!r}"
            )
        logger.info("Primary Group search set to: %s", result)

    async def change_business_type(self, value: str) -> None:
        await self.open_customer_details_tab()
        result = await self.field_actions.set_field("Business Type", value, "combobox")
        logger.info("Changed Business Type to: %s", result)
        await self.cancellable_sleep(800)

    async def load_customer(
        self,
        *,
        customer_number: str | None = None,
        account_group: str | None = None,
        distribution_channel: str | None = None,
        sales_office: str | None = None,
        account_name: str | None = None,
    ) -> None:
        await self._ensure_on_form_page()
        if await self.is_customer_loaded(customer_number):
            logger.info(
                "Customer %s already loaded — skipping search",
                customer_number or account_name or "current",
            )
            return

        scope = await self._ensure_form_scope("Customer Number")
        await self.open_customer_search()

        if customer_number:
            query = customer_number
        elif account_name:
            query = account_name
        else:
            query = default_customer_search_query()

        self._last_customer_number = query
        await type_in_input(scope, "Customer Number", query)
        await self.wait_for_customer_dropdown()

        matched = False
        if customer_number:
            matched = await self._select_customer_row_by_number(customer_number)
        if not matched:
            await self.select_first_customer_from_dropdown()
        await self.search()
        await self.wait_for_data()
        from app.automation.workspace_tab import _form_visible

        if await _form_visible(self.page):
            self._pinned_form_page = self.page

    async def load_customer_by_saved_query(
        self,
        *,
        soql_text: str,
        account_number: str | None = None,
        customer_number: str | None = None,
        account_group: str | None = None,
        distribution_channel: str | None = None,
        sales_office: str | None = None,
        account_name: str | None = None,
    ) -> str:
        """Run saved SOQL via REST API, then load the chosen account in the form."""
        resolved_number = account_number
        resolved_customer = customer_number
        resolved_name = account_name
        resolved_group = account_group
        resolved_channel = distribution_channel
        resolved_office = sales_office

        if not resolved_number and not resolved_customer:
            if self.org is None:
                raise SoqlError(
                    "Account SOQL lookup requires a connected Salesforce org with credentials"
                )
            client = SoqlClient(
                org=self.org, credentials=self.credentials, page=self.page
            )
            try:
                result = await client.query(soql_text, limit=1)
            except (SoqlAuthError, SoqlExecutionError) as exc:
                raise SoqlError(
                    f"Failed to run account query via Salesforce REST API: {exc}"
                ) from exc
            if not result.records:
                raise SoqlError("Account SOQL query returned no rows")
            row = result.records[0]
            resolved_number = row.account_number
            resolved_customer = row.customer_number or row.account_number
            resolved_name = resolved_name or row.account_name
            resolved_group = resolved_group or row.account_group
            resolved_channel = resolved_channel or row.distribution_channel
            resolved_office = resolved_office or row.sales_office

        search_number = resolved_customer or resolved_number
        if not search_number and not resolved_name:
            raise SoqlError("Account query did not yield an account number or name")

        await self._ensure_on_form_page()
        if await self.is_customer_loaded(search_number):
            logger.info("Customer %s already loaded via query — skipping search", search_number)
            return search_number or resolved_name or ""

        await self.load_customer(
            customer_number=search_number,
            account_group=resolved_group,
            distribution_channel=resolved_channel,
            sales_office=resolved_office,
            account_name=resolved_name if not search_number else None,
        )
        from app.automation.workspace_tab import _form_visible

        if await _form_visible(self.page):
            self._pinned_form_page = self.page
        if not await self.is_customer_loaded(search_number):
            raise SoqlError(
                f"Customer {search_number} did not load — "
                "customer lookup or Primary Group data is still empty"
            )
        return search_number or resolved_name or ""

    async def _select_customer_row_by_number(
        self, account_number: str, *, timeout_ms: int = 6000
    ) -> bool:
        """Click the dropdown row whose visible text starts with the account number.

        Returns True when a matching row was clicked; False when nothing matched
        (caller can fall back to the first row).
        """
        scope = await self._ensure_form_scope("Customer Number")
        prefix = (account_number or "").strip()
        if not prefix:
            return False

        deadline_steps = max(1, int(timeout_ms / 300))
        pattern = re.compile(rf"^\s*0*{re.escape(prefix)}\b")
        for _ in range(deadline_steps):
            self._check_cancelled()
            try:
                rows = scope.get_by_text(pattern)
                count = await rows.count()
            except Exception:
                count = 0

            for idx in range(min(count, 10)):
                row = rows.nth(idx)
                try:
                    if not await row.is_visible(timeout=300):
                        continue
                    text = (await row.text_content() or "").strip()
                    if not text:
                        continue
                    if not text.lstrip("0").startswith(prefix.lstrip("0")):
                        continue
                    await row.scroll_into_view_if_needed(timeout=1000)
                    await row.click(timeout=2000)
                    logger.info(
                        "Selected customer dropdown row matching account %s: %s",
                        account_number,
                        text[:80],
                    )
                    return True
                except Exception as exc:
                    logger.debug("Row click attempt failed: %s", exc)
                    continue
            await self.cancellable_sleep(300)
        logger.info(
            "No dropdown row matched account number %s — falling back to first row",
            account_number,
        )
        return False

    async def _click_submit(self) -> None:
        await self._ensure_on_form_page()
        scope = await self._ensure_form_scope("Primary Group")
        if not await field_present(scope, "Primary Group"):
            scope = await self._ensure_form_scope("Customer Number")
        from app.automation.form_field import click_form_button

        await click_form_button(scope, "Submit")
        await self.cancellable_sleep(1500)
        logger.info("Clicked Submit")

    async def submit(
        self,
        *,
        bottler_id: str | None = None,
        max_attempts: int = 3,
    ) -> list[str]:
        """Submit with required-field healing; returns auto-fill log lines."""
        from app.automation.form_validation import detect_submit_outcome, scan_empty_required_fields
        from app.services.required_field_filler import (
            fill_empty_required_for_bottler,
            fill_missing_fields,
        )

        resolved_bottler = resolve_bottler_id(
            bottler_id=bottler_id,
            org=self.org,
            customer_target=None,
        )
        logs: list[str] = []

        if resolved_bottler:
            logs.extend(
                await fill_empty_required_for_bottler(
                    self.page,
                    bottler_id=resolved_bottler,
                    field_actions=self.field_actions,
                    data_change_page=self,
                    db=self.db,
                )
            )

        for attempt in range(max_attempts):
            self._check_cancelled()
            await self._click_submit()
            outcome = await detect_submit_outcome(
                self.page, bottler_id=resolved_bottler, db=self.db
            )
            if outcome.status == "success":
                logger.info("Submit succeeded: %s", outcome.message[:200])
                return logs

            missing = list(outcome.missing_field_labels or [])
            if resolved_bottler and not missing:
                missing = await scan_empty_required_fields(
                    self.page, resolved_bottler, db=self.db
                )

            if not missing:
                raise RuntimeError(
                    outcome.message or "Submit failed with no identifiable missing fields"
                )

            logger.info(
                "Submit validation blocked (attempt %d/%d), filling: %s",
                attempt + 1,
                max_attempts,
                missing,
            )
            logs.extend(
                await fill_missing_fields(
                    self.page,
                    missing,
                    bottler_id=resolved_bottler or "",
                    field_actions=self.field_actions,
                    data_change_page=self,
                    db=self.db,
                )
            )

        raise RuntimeError("Submit blocked after filling required fields")

    async def select_module(self, module: str) -> None:
        locator = self.resolve_locator("data_change.module_selection")
        await locator.select_option(label=module)
        logger.info("Selected module: %s", module)

    async def wait_for_customer_dropdown(self, timeout: int = 20_000) -> None:
        """Wait for customer search results after typing in the lookup/search field."""
        scope = await self._ensure_form_scope("Customer Number")
        query = getattr(self, "_last_customer_number", None) or default_customer_search_query()

        elapsed = 0
        while elapsed < timeout:
            self._check_cancelled()
            if await customer_lookup_visible(scope, "Customer Number"):
                logger.info("Customer search results are visible")
                return

            inp = await find_input(scope, "Customer Number")
            current = (await inp.input_value() or "").strip().lower()
            if not current or current in ("search customer...", "search customer"):
                await inp.click(timeout=5000)
                await inp.fill(query)
                self._last_customer_number = query
                await self.cancellable_sleep(900)
            elif len(current) < 3 and current.isdigit():
                await inp.fill(query)
                self._last_customer_number = query
                await self.cancellable_sleep(900)
            else:
                await inp.click(timeout=3000)
                await self.cancellable_sleep(400)

            elapsed += 400

        await self.screenshot("customer_dropdown_not_visible")
        raise TimeoutError(
            "Customer search results did not appear — type in Customer Name/Number and pick a row"
        )

    async def wait_for_data(self, timeout: int = 30_000) -> None:
        elapsed = 0
        while elapsed < timeout:
            self._check_cancelled()
            if await self._customer_field_confirmed() and await self._primary_group_populated():
                logger.info("Customer data loaded — customer selected and Primary Group populated")
                return
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
