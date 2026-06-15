import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Awaitable
from uuid import UUID

from playwright.async_api import Page

from app.agents.state import ExecutionState
from app.automation.pages import (
    AppLauncherPage,
    CustomerLifecyclePage,
    DataChangePage,
    LoginPage,
    OnboardingPage,
)
from app.automation.expected_validator import check_expected
from app.automation.salesforce_utils import normalize_app_name
from app.schemas.agent import PlannedStep, StepResult
from app.services.execution_registry import ExecutionCancelled, execution_registry

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
    ):
        self.page = page
        self.artifacts_dir = artifacts_dir
        self.credentials = credentials
        self.login_url = login_url
        self.auth_method = auth_method
        self.execution_id = execution_id
        self.template_key = template_key
        self.db = db

        self.login_page = LoginPage(page, artifacts_dir, execution_id)
        self.app_launcher = AppLauncherPage(page, artifacts_dir, execution_id)
        self.onboarding = OnboardingPage(page, artifacts_dir, execution_id)
        self.customer_lifecycle = CustomerLifecyclePage(page, artifacts_dir, execution_id)
        self.data_change = DataChangePage(
            page, artifacts_dir, execution_id, template_key=template_key, db=db
        )

    def _sync_page(self, page: Page) -> None:
        """Keep all page objects on the active browser tab."""
        self.page = page
        self.login_page.page = page
        self.app_launcher.page = page
        self.onboarding.page = page
        self.customer_lifecycle.page = page
        self.data_change.page = page

    async def execute(self, step: PlannedStep) -> StepResult:
        logs: list[str] = []
        try:
            match step.action:
                case "login":
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
                    await self.customer_lifecycle.wait_for_queues_ready()
                    logs.append("Login successful — landed on Customer Life Cycle Queues")
                case "open_app_launcher":
                    if not await self.customer_lifecycle.is_on_queues_page():
                        await self.app_launcher.open()
                        logs.append("App Launcher opened")
                    else:
                        logs.append("Skipped App Launcher — already on Queues page")
                case "open_app":
                    if not await self.customer_lifecycle.is_on_queues_page():
                        app = normalize_app_name(step.params.get("app"))
                        await self.app_launcher.search_and_open_app(app)
                        logs.append(f"Opened app: {app}")
                    else:
                        logs.append("Skipped open app — already on Queues page")
                case "open_tab":
                    await self.onboarding.open_customer_lifecycle()
                    logs.append("On Customer Life Cycle Queues tab")
                case "open_queues":
                    await self.customer_lifecycle.open_queues_object()
                    logs.append("Opened Customer Life Cycle Queue object")
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
                    logs.append(f"Clicked '{button_label}' and selected '{menu_option}'")
                case "search_select_customer":
                    query = (
                        step.params.get("customer_query")
                        or step.params.get("customer_number")
                        or self.credentials.get("customer_number", "12345678")
                    )
                    await self.data_change.search_and_select_customer(query)
                    logs.append(f"Selected customer: {query}")
                case "open_customer_details":
                    await self.data_change.open_customer_details_tab()
                    self._sync_page(self.data_change.page)
                    logs.append("Opened Customer Details tab")
                case "modify_primary_group":
                    value = step.params.get("primary_group", "__any__")
                    await self.data_change.modify_primary_group(value)
                    self._sync_page(self.data_change.page)
                    logs.append(f"Modified Primary Group: {value}")
                case "submit":
                    await self.data_change.submit()
                    self._sync_page(self.data_change.page)
                    logs.append("Submitted Data Change Request")
                case "click_new":
                    await self.customer_lifecycle.click_new_request()
                    logs.append("Clicked New Request")
                case "select_request_module":
                    module_option = step.params.get("module_option", "NEW DATA CHANGE")
                    await self.customer_lifecycle.select_request_module(module_option)
                    self._sync_page(self.customer_lifecycle.page)
                    logs.append(f"Selected request module: {module_option}")
                case "select_module":
                    module = step.params.get("module", "NEW DATA CHANGE")
                    await self.customer_lifecycle.select_request_module(module)
                    self._sync_page(self.customer_lifecycle.page)
                    logs.append(f"Selected module: {module}")
                case "select_sales_office":
                    office = step.params.get("office", "__any__")
                    await self.data_change.focus_form()
                    selected_office = await self.data_change.select_sales_office(office)
                    self._sync_page(self.data_change.page)
                    logs.append(f"Selected sales office: {selected_office}")
                case "open_customer_search":
                    await self.data_change.open_customer_search()
                    logs.append("Opened customer search field")
                case "enter_customer_number":
                    customer_number = (
                        step.params.get("customer_number")
                        or self.credentials.get("customer_number", "060")
                    )
                    await self.data_change.enter_customer_number(customer_number)
                    self._sync_page(self.data_change.page)
                    logs.append(f"Entered customer number: {customer_number}")
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
                case "validate_expected":
                    expected = step.params.get("expected", "")
                    passed, detail = await check_expected(self.page, expected)
                    if not passed:
                        raise RuntimeError(detail)
                    logs.append(detail)
                case "set_field":
                    field = step.params.get("field", "")
                    value = step.params.get("value")
                    field_type = step.params.get("field_type")
                    result = await self.data_change.field_actions.set_field(field, value, field_type)
                    logs.append(f"Set {field} = {result}")
                case "save_draft":
                    await self.data_change.save_draft()
                    logs.append("Save draft executed")
                case _:
                    raise RuntimeError(
                        f"Unknown action '{step.action}' — not implemented in executor. "
                        f"Supported actions: {', '.join(sorted(EXECUTOR_ACTIONS))}"
                    )

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
            logger.exception("Step %s failed: %s", step.name, exc)
            screenshot = await self.data_change.screenshot(f"step_{step.seq:02d}_{step.action}_error")
            return StepResult(
                seq=step.seq,
                name=step.name,
                action=step.action,
                status="failed",
                screenshot_path=screenshot,
                error=str(exc),
                logs=logs,
            )


async def executor_node(state: ExecutionState, page: Page, on_event: EventCallback | None = None) -> dict:
    planned_steps = state.get("planned_steps", [])
    current_index = state.get("current_step_index", 0)
    step_results = list(state.get("step_results", []))
    artifacts_dir = Path(state.get("artifacts_dir", "./artifacts"))

    if current_index >= len(planned_steps):
        return {"current_step_index": current_index}

    step = planned_steps[current_index]
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

    executor = StepExecutor(
        page=page,
        artifacts_dir=artifacts_dir,
        credentials=state.get("org_credentials", {}),
        login_url=state.get("login_url", ""),
        auth_method=state.get("auth_method", "credentials"),
        execution_id=execution_id,
        template_key=state.get("template_key", "DATA_CHANGE_REQUEST"),
    )

    try:
        result = await executor.execute(step)
    except ExecutionCancelled:
        raise
    step_results.append(result)

    if on_event:
        await on_event(
            event_type="step_completed",
            step_seq=step.seq,
            step_name=step.name,
            status=result.status,
            message=result.error or f"Completed: {step.name}",
            screenshot_path=result.screenshot_path,
        )

    if result.status == "failed":
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 2)
        if retry_count < max_retries:
            return {
                "step_results": step_results,
                "retry_count": retry_count + 1,
            }
        return {
            "step_results": step_results,
            "current_step_index": len(planned_steps),
            "error": result.error,
        }

    return {
        "step_results": step_results,
        "current_step_index": current_index + 1,
        "retry_count": 0,
    }
