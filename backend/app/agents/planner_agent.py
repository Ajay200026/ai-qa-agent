import logging

from app.agents.state import ExecutionState
from app.core.database import AsyncSessionLocal
from app.schemas.agent import PlannedStep
from app.services.workflow_service import WorkflowService
from app.workflows.scenario_text_parser import parse_scenario_text

logger = logging.getLogger(__name__)

ACTION_WHITELIST = {
    "login",
    "open_queues",
    "create_data_change_request",
    "search_select_customer",
    "open_customer_details",
    "modify_primary_group",
    "submit",
    "click_new_button",
    "select_request_module",
    "wait_for_customer_dropdown",
    "select_first_customer",
    "open_app_launcher",
    "open_app",
    "open_tab",
    "click_new",
    "select_module",
    "select_sales_office",
    "open_customer_search",
    "enter_customer_number",
    "search",
    "wait_for_data",
    "save_draft",
    "validate",
    "validate_expected",
    "set_field",
}


async def planner_node(state: ExecutionState) -> dict:
    parsed = state.get("parsed_scenario")
    if not parsed:
        from app.schemas.parsed_scenario import ParsedScenario

        parsed = parse_scenario_text(
            "\n".join(
                filter(
                    None,
                    [
                        state.get("scenario_description", ""),
                        state.get("acceptance_criteria", ""),
                    ],
                )
            ),
            template_key=state.get("template_key"),
            inputs=state.get("inputs"),
            business_actions=state.get("business_actions"),
            expected_results=state.get("expected_results"),
        )
        if isinstance(parsed, dict):
            parsed = ParsedScenario(**parsed)

    async with AsyncSessionLocal() as db:
        service = WorkflowService(db)
        planned_steps, plan = await service.build_plan(parsed)

    logger.info(
        "Planned %d steps via workflow template %s",
        len(planned_steps),
        parsed.template_key,
    )
    return {
        "planned_steps": planned_steps,
        "plan": plan,
        "expected_results": parsed.expected_results,
        "template_key": parsed.template_key,
        "current_step_index": 0,
        "retry_count": 0,
        "max_retries": 1,
        "step_results": [],
    }
