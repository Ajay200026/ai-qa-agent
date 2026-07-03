import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Awaitable
from uuid import UUID

from playwright.async_api import Page

from app.knowledge.data_change_field_registry import default_customer_search_query

from app.agents.state import ExecutionState
from app.automation.assertions import assert_no_toast, run_assertion, wait_for_toast
from app.automation.combobox import is_auto_pick
from app.automation.field_state import get_field_value, is_field_editable, is_field_readonly
from app.automation.pages import (
    AppLauncherPage,
    CustomerLifecyclePage,
    DataChangePage,
    LoginPage,
    OnboardingPage,
)
from app.automation.self_healing import retry_with_heal
from app.automation.expected_validator import check_expected
from app.automation.salesforce_utils import normalize_app_name
from app.automation.workspace_tab import _form_visible, find_data_change_page, resolve_execution_page
from app.schemas.agent import PlannedStep, StepResult
from app.schemas.test_case import Assertion, AssertionKind
from app.services.execution_registry import ExecutionCancelled, execution_registry
from app.services.login_resolver import LoginResolver, LoginResolverError

from app.workflows.merger import EXECUTOR_ACTIONS

logger = logging.getLogger(__name__)

EventCallback = Callable[..., Awaitable[None]]


class StepExecutor:
    def __init__(
        self,
        page: Page,
        artifacts_dir: Path,
        credentials: dict,
        login_url: str,
        auth_method: str,
        execution_id: UUID | None = None,
        template_key: str = "DATA_CHANGE_REQUEST",
        db=None,
        continue_on_failure: bool = False,
        max_step_retries: int = 2,
        org=None,
        instance_url: str | None = None,
    ):
        self.page = page
        self.artifacts_dir = artifacts_dir
        self.credentials = credentials
        self.login_url = login_url
        self.auth_method = auth_method
        self.execution_id = execution_id
        self.template_key = template_key
        self.db = db
        self.continue_on_failure = continue_on_failure
        self.max_step_retries = max_step_retries
        self.org = org
        self.instance_url = instance_url
        self._login_resolver: LoginResolver | None = None

        self.login_page = LoginPage(page, artifacts_dir, execution_id)
        self.app_launcher = AppLauncherPage(page, artifacts_dir, execution_id)
        self.onboarding = OnboardingPage(page, artifacts_dir, execution_id)
        self.customer_lifecycle = CustomerLifecyclePage(page, artifacts_dir, execution_id)
        self.data_change = DataChangePage(
            page,
            artifacts_dir,
            execution_id,
            template_key=template_key,
            db=db,
            org=org,
            credentials=credentials,
        )

    def _sync_page(self, page: Page) -> None:
        self.page = page
        self.login_page.page = page
        self.app_launcher.page = page
        self.onboarding.page = page
        self.customer_lifecycle.page = page
        self.data_change.page = page
        if self._login_resolver is not None:
            self._login_resolver.sync_page(page)

    async def _ensure_active_page(self) -> None:
        pinned = getattr(self.data_change, "_pinned_form_page", None)
        if pinned and not pinned.is_closed() and await _form_visible(pinned):
            if self.page is not pinned:
                await pinned.bring_to_front()
            self._sync_page(pinned)
            return
        if await _form_visible(self.page):
            return
        if len(self.page.context.pages) <= 1:
            return
        found = await find_data_change_page(self.page)
        if found and found is not self.page:
            self._sync_page(found)
            self.data_change._pinned_form_page = found

    def _get_login_resolver(self) -> LoginResolver:
        if self._login_resolver is None:
            if self.org is None:
                raise LoginResolverError(
                    "LoginResolver requires the Salesforce org context "
                    "(executor was constructed without org)"
                )
            self._login_resolver = LoginResolver(
                page=self.page,
                org=self.org,
                credentials=self.credentials,
                artifacts_dir=self.artifacts_dir,
                execution_id=self.execution_id,
            )
        return self._login_resolver

    async def execute(self, step: PlannedStep) -> StepResult:
        await self._ensure_active_page()
        logs: list[str] = []
        last_exc: Exception | None = None

        for attempt in range(self.max_step_retries + 1):
            if attempt > 0:
                logs.append(f"retry attempt {attempt}")
                await self.page.wait_for_timeout(500 * attempt)
            try:
                await self._run_action(step, logs)
                screenshot = await self.data_change.screenshot(f"step_{step.seq:02d}_{step.action}")
                return StepResult(
                    seq=step.seq,
                    name=step.name,
                    action=step.action,
                    status="passed",
                    screenshot_path=screenshot,
                    logs=logs,
                )
            except ExecutionCancelled:
                raise
            except Exception as exc:
                if self.execution_id and execution_registry.is_cancelled(self.execution_id):
                    raise ExecutionCancelled(str(exc)) from exc
                last_exc = exc
                logger.warning("Step %s attempt %d failed: %s", step.name, attempt + 1, exc)
                if attempt >= self.max_step_retries:
                    break

        logger.exception("Step %s failed after retries: %s", step.name, last_exc)
        screenshot = await self.data_change.screenshot(f"step_{step.seq:02d}_{step.action}_error")
        return StepResult(
            seq=step.seq,
            name=step.name,
            action=step.action,
            status="failed",
            screenshot_path=screenshot,
            error=str(last_exc),
            logs=logs,
        )

    async def _run_action(self, step: PlannedStep, logs: list[str]) -> None:
        async def heal() -> None:
            await self.data_change.wait_for_lightning_ready(timeout=10_000)

        match step.action:
            case "login":
                await retry_with_heal(lambda: self._login(), heal_fn=heal)
                logs.append("Login successful")
            case "login_as":
                bottler_id = (
                    step.params.get("bottler_id")
                    or step.params.get("bottler")
                    or ""
                )
                onboarding_role = (
                    step.params.get("onboarding_role")
                    or step.params.get("role")
                    or ""
                )
                if not bottler_id or not onboarding_role:
                    raise RuntimeError(
                        "login_as requires bottler_id and onboarding_role"
                    )
                resolver = self._get_login_resolver()
                result = await resolver.login_as(bottler_id, onboarding_role)
                self._sync_page(self.page)
                # Privacy: log only user_id + bottler/role, never username.
                logs.append(
                    f"Impersonated user_id={result.user_id} "
                    f"bottler={bottler_id} role={onboarding_role}"
                )
            case "open_app_launcher":
                if not await self.customer_lifecycle.is_on_queues_page():
                    await self.app_launcher.open()
                    logs.append("App Launcher opened")
            case "open_app":
                if not await self.customer_lifecycle.is_on_queues_page():
                    app = normalize_app_name(step.params.get("app"))
                    await self.app_launcher.search_and_open_app(app)
                    logs.append(f"Opened app: {app}")
            case "open_tab":
                await self.onboarding.open_customer_lifecycle()
                logs.append("On Customer Life Cycle | Queue tab")
            case "open_queues":
                await self.customer_lifecycle.open_queues_object()
                self._sync_page(self.customer_lifecycle.page)
                logs.append("Opened Customer Life Cycle | Queue")
            case "click_new_button":
                button_label = step.params.get("button_label", "New")
                await self.customer_lifecycle.click_new_button(button_label)
                logs.append(f"Clicked '{button_label}' button")
            case "create_data_change_request":
                button_label = step.params.get("button_label", "New")
                menu_option = step.params.get("menu_option", "NEW DATA CHANGE")
                await self.customer_lifecycle.create_data_change_request(
                    button_label=button_label,
                    menu_option=menu_option,
                )
                logs.append(f"Created data change: {menu_option}")
            case "search_select_customer":
                query = (
                    step.params.get("customer_query")
                    or step.params.get("customer_number")
                    or self.credentials.get("customer_number")
                )
                if not query:
                    raise RuntimeError("blocked - missing input: customer_number required")
                await self.data_change.search_and_select_customer(query)
                logs.append(f"Selected customer: {query}")
            case "load_customer":
                customer_number = (
                    step.params.get("customer_number")
                    or step.params.get("value")
                    or self.credentials.get("customer_number")
                )
                account_group = step.params.get("account_group")
                distribution_channel = step.params.get("distribution_channel")
                sales_office = step.params.get("sales_office")
                account_name = step.params.get("account_name")
                if not customer_number and not account_name:
                    await self.data_change.search_and_select_customer("__first__")
                    logs.append("Loaded first available customer")
                else:
                    await self.data_change.load_customer(
                        customer_number=customer_number,
                        account_group=account_group,
                        distribution_channel=distribution_channel,
                        sales_office=sales_office,
                        account_name=account_name,
                    )
                    label = customer_number or account_name
                    logs.append(f"Loaded customer: {label}")
            case "load_customer_by_query":
                soql_text = step.params.get("soql_text") or ""
                if not soql_text:
                    raise RuntimeError("load_customer_by_query requires soql_text")
                selected = await self.data_change.load_customer_by_saved_query(
                    soql_text=soql_text,
                    account_number=step.params.get("account_number"),
                    customer_number=step.params.get("customer_number"),
                    account_group=step.params.get("account_group"),
                    distribution_channel=step.params.get("distribution_channel"),
                    sales_office=step.params.get("sales_office"),
                    account_name=step.params.get("account_name"),
                )
                self._sync_page(self.data_change.page)
                search_num = (
                    step.params.get("customer_number")
                    or step.params.get("account_number")
                    or selected
                )
                if not await self.data_change.is_customer_loaded(search_num):
                    raise RuntimeError(
                        "Customer query step finished but form data is not loaded — "
                        "customer lookup or Primary Group is still empty"
                    )
                logs.append(f"Loaded customer via saved query (account={selected})")
                await self.data_change.open_customer_details_tab()
                self._sync_page(self.data_change.page)
                logs.append("Customer Details ready for Primary Group update")
            case "open_customer_details":
                await self.data_change.open_customer_details_tab()
                self._sync_page(self.data_change.page)
                logs.append("Customer Details section ready")
            case "modify_primary_group":
                value = step.params.get("primary_group", "__any__")
                await self.data_change.modify_primary_group(value)
                self._sync_page(self.data_change.page)
                logs.append(f"Modified Primary Group: {value}")
            case "change_business_type":
                value = step.params.get("value")
                if not value:
                    raise RuntimeError("blocked - missing input: Business Type value required")
                await self.data_change.change_business_type(value)
                self._sync_page(self.data_change.page)
                logs.append(f"Changed Business Type: {value}")
            case "submit":
                bottler_id = (
                    step.params.get("bottler_id")
                    or step.params.get("bottler")
                    or getattr(self.org, "bottler", None)
                )
                fill_logs = await self.data_change.submit(bottler_id=bottler_id)
                self._sync_page(self.data_change.page)
                logs.extend(fill_logs)
                logs.append("Submitted Data Change Request")
            case "click_new":
                await self.customer_lifecycle.click_new_request()
                logs.append("Clicked New Request")
            case "select_request_module" | "select_module":
                module_option = step.params.get("module_option") or step.params.get("module", "NEW DATA CHANGE")
                await self.customer_lifecycle.select_request_module(module_option)
                self._sync_page(self.customer_lifecycle.page)
                await self.data_change.focus_form()
                self.data_change._pinned_form_page = self.data_change.page
                logs.append(f"Selected request module: {module_option}")
            case "select_sales_office":
                office = step.params.get("office", "__any__")
                if is_auto_pick(office):
                    logs.append(
                        "Skipping sales office — system will set it from customer search"
                    )
                else:
                    bottler_id = (
                        step.params.get("bottler_id")
                        or step.params.get("bottler")
                        or getattr(self.org, "bottler", None)
                    )
                    await self.data_change.focus_form()
                    selected_office = await self.data_change.select_sales_office(
                        office, bottler_id=bottler_id
                    )
                    self._sync_page(self.data_change.page)
                    logs.append(f"Selected sales office: {selected_office}")
            case "open_customer_search":
                await self.data_change.open_customer_search()
                logs.append("Opened customer search field")
            case "enter_customer_number":
                customer_number = (
                    step.params.get("customer_number")
                    or self.credentials.get("customer_number")
                )
                if not customer_number or customer_number in ("__first__", "__any__"):
                    customer_number = default_customer_search_query()
                await self.data_change.enter_customer_number(customer_number)
                self._sync_page(self.data_change.page)
                logs.append(f"Entered customer search query: {customer_number}")
            case "wait_for_customer_dropdown":
                await self.data_change.wait_for_customer_dropdown()
                self._sync_page(self.data_change.page)
                logs.append("Customer search dropdown appeared")
            case "select_first_customer":
                await self.data_change.select_first_customer_from_dropdown()
                self._sync_page(self.data_change.page)
                logs.append("Selected first customer from dropdown")
            case "search":
                await self.data_change.search()
                self._sync_page(self.data_change.page)
                logs.append("Search executed")
            case "wait_for_data":
                await self.data_change.wait_for_data()
                self._sync_page(self.data_change.page)
                logs.append("Data load wait completed")
            case "check_field_editable":
                field = step.params.get("field") or "Primary Group"
                passed, detail = await is_field_editable(self.page, field, self.db)
                if not passed:
                    raise RuntimeError(detail)
                logs.append(detail)
            case "check_field_readonly":
                field = step.params.get("field") or "Business Type Extension"
                passed, detail = await is_field_readonly(self.page, field, self.db)
                if not passed:
                    raise RuntimeError(detail)
                logs.append(detail)
            case "read_toast":
                expected = step.params.get("expected") or step.params.get("value")
                toast = await wait_for_toast(self.page)
                if not toast:
                    raise RuntimeError("No toast appeared")
                if expected and expected.lower() not in toast.lower():
                    raise RuntimeError(f"Toast mismatch: got {toast!r}, expected {expected!r}")
                logs.append(f"Toast: {toast}")
            case "assert_no_toast":
                passed, detail = await assert_no_toast(self.page)
                if not passed:
                    raise RuntimeError(detail)
                logs.append(detail)
            case "validate_expected":
                expected = step.params.get("expected", "")
                passed, detail, _ = await _validate_expected(self.page, expected, self.db)
                if not passed:
                    raise RuntimeError(detail)
                logs.append(detail)
            case "set_field":
                field = step.params.get("field", "")
                if not field:
                    raise RuntimeError("blocked - missing input: field name required")
                value = step.params.get("value")
                field_type = step.params.get("field_type")
                result = await self.data_change.field_actions.set_field(field, value, field_type)
                logs.append(f"Set {field} = {result}")
            case "save_draft":
                await self.data_change.save_draft()
                logs.append("Save draft executed")
            case _:
                raise RuntimeError(
                    f"Unknown action '{step.action}' — not implemented. "
                    f"Supported: {', '.join(sorted(EXECUTOR_ACTIONS))}"
                )

    async def _login(self) -> None:
        if await self.login_page.is_logged_in():
            logger.info(
                "Skipping login — Salesforce session already active at %s",
                self.page.url,
            )
            return
        if self.auth_method == "oauth":
            await self.login_page.login_with_oauth(
                self.credentials["instance_url"],
                self.credentials["access_token"],
            )
        else:
            await self.login_page.login_with_credentials(
                self.login_url,
                self.credentials["username"],
                self.credentials["password"],
            )


async def _validate_expected(page: Page, expected: str, db=None) -> tuple[bool, str, str | None]:
    from app.workflows.action_mapping import infer_assertions_from_expected

    assertions = infer_assertions_from_expected(expected)
    if assertions:
        for assertion in assertions:
            passed, detail, actual = await run_assertion(page, assertion, db=db)
            if not passed:
                return False, detail, actual
        return True, f"Validated: {expected}", None
    return await check_expected(page, expected, db=db) + (None,)


async def executor_node(state: ExecutionState, page: Page, on_event: EventCallback | None = None) -> dict:
    if not await _form_visible(page) and len(page.context.pages) > 1:
        page = await resolve_execution_page(page)
    planned_steps = state.get("planned_steps", [])
    current_index = state.get("current_step_index", 0)
    step_results = list(state.get("step_results", []))
    artifacts_dir = Path(state.get("artifacts_dir", "./artifacts"))
    continue_on_failure = state.get("continue_on_failure", False)

    if current_index >= len(planned_steps):
        return {"current_step_index": current_index}

    step = planned_steps[current_index]
    step_retry_key = f"step_retry_{step.seq}"
    step_retries = state.get(step_retry_key, 0)
    max_retries = state.get("max_retries", 2)

    if on_event:
        await on_event(
            event_type="step_started",
            step_seq=step.seq,
            step_name=step.name,
            status="running",
            message=f"Executing: {step.name}",
        )

    execution_id = state.get("execution_id")
    execution_registry.check_cancelled(execution_id)

    org_shim = SimpleNamespace(
        id=state.get("org_id") or execution_id,
        login_url=state.get("login_url", ""),
        auth_method=state.get("auth_method", "credentials"),
        instance_url=state.get("instance_url"),
    )

    executor = StepExecutor(
        page=page,
        artifacts_dir=artifacts_dir,
        credentials=state.get("org_credentials", {}),
        login_url=state.get("login_url", ""),
        auth_method=state.get("auth_method", "credentials"),
        execution_id=execution_id,
        template_key=state.get("template_key", "DATA_CHANGE_REQUEST"),
        continue_on_failure=continue_on_failure,
        max_step_retries=max_retries,
        org=org_shim,
        instance_url=state.get("instance_url"),
    )

    try:
        result = await executor.execute(step)
    except ExecutionCancelled:
        raise

    updates: dict = {step_retry_key: 0}

    if result.status == "failed":
        if step_retries < max_retries:
            updates[step_retry_key] = step_retries + 1
            updates["active_page"] = executor.page
            return updates

        step_results.append(result)
        updates["step_results"] = step_results

        if continue_on_failure:
            updates["current_step_index"] = current_index + 1
            updates["error"] = None
        else:
            updates["current_step_index"] = len(planned_steps)
            updates["error"] = result.error
    else:
        step_results.append(result)
        updates["step_results"] = step_results
        updates["current_step_index"] = current_index + 1
        updates["error"] = None

    if on_event:
        await on_event(
            event_type="step_completed",
            step_seq=step.seq,
            step_name=step.name,
            status=result.status,
            message=result.error or f"Completed: {step.name}",
            screenshot_path=result.screenshot_path,
        )

    updates["active_page"] = executor.page
    return updates
