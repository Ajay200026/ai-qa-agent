import re

from app.schemas.agent import ExecutionPlan, ExecutionPlanStep, PlannedStep
from app.workflows.base import DatabaseWorkflowStrategy

# Actions the StepExecutor actually implements.
EXECUTOR_ACTIONS = frozenset({
    "login",
    "open_app_launcher",
    "open_app",
    "open_tab",
    "open_queues",
    "click_new_button",
    "create_data_change_request",
    "search_select_customer",
    "open_customer_details",
    "modify_primary_group",
    "submit",
    "click_new",
    "select_request_module",
    "select_module",
    "select_sales_office",
    "open_customer_search",
    "enter_customer_number",
    "wait_for_customer_dropdown",
    "select_first_customer",
    "search",
    "wait_for_data",
    "validate_expected",
    "set_field",
    "save_draft",
})

ACTION_MAP = {
    "open customer details": "open_customer_details",
    "open_customer_details": "open_customer_details",
    "navigate to customer details section": "open_customer_details",
    "navigate to customer details": "open_customer_details",
    "update primary group": "modify_primary_group",
    "modify primary group": "modify_primary_group",
    "modify_primary_group": "modify_primary_group",
    "submit": "submit",
    "click submit": "submit",
    "save draft": "save_draft",
    "validate": "validate_expected",
}

BUSINESS_ACTION_ALIASES = {
    "update_primary_group": "modify_primary_group",
    "click_submit": "submit",
    "navigate_to_customer_details_section": "open_customer_details",
    "select_any_available_option_from_the_dropdown_list": "modify_primary_group",
}

# Verbose LLM micro-steps collapsed into modify_primary_group / skipped.
MICRO_STEP_PATTERNS = (
    re.compile(r"locate.*primary", re.I),
    re.compile(r"wait.*dropdown", re.I),
    re.compile(r"wait.*search\s+results", re.I),
    re.compile(r"click.*primary.*search", re.I),
    re.compile(r"verify.*primary.*(populated|value)", re.I),
)


class PlanMerger:
    def __init__(self, strategy: DatabaseWorkflowStrategy):
        self.strategy = strategy

    def merge(
        self,
        business_actions: list[dict],
        expected_results: list[str],
    ) -> tuple[list[PlannedStep], ExecutionPlan]:
        planned: list[PlannedStep] = []
        plan_steps: list[ExecutionPlanStep] = []
        seq = 1

        for step_def in self.strategy._template_steps:
            if not self.strategy._should_include_step(step_def):
                continue
            params = self.strategy._substitute_params(step_def.get("params", {}))
            planned.append(
                PlannedStep(
                    seq=seq,
                    name=step_def["name"],
                    action=step_def["action"],
                    params=params,
                )
            )
            plan_steps.append(
                ExecutionPlanStep(
                    action=step_def["action"],
                    description=step_def["name"],
                    value=str(params) if params else None,
                )
            )
            seq += 1

        primary_group_value: str | None = None
        open_details = False
        do_submit = False
        saw_primary_group_flow = False
        extra_actions: list[dict] = []

        for raw_action in business_actions:
            action_name = raw_action.get("action") if isinstance(raw_action, dict) else str(raw_action)
            desc = raw_action.get("description", action_name) if isinstance(raw_action, dict) else action_name
            combined = f"{action_name} {desc}".lower()
            if "primary" in combined and "group" in combined:
                saw_primary_group_flow = True

            action_def = self._normalize_business_action(raw_action)
            if action_def is None:
                continue
            action = action_def["action"]
            if action == "open_customer_details":
                open_details = True
            elif action == "modify_primary_group":
                value = action_def["params"].get("primary_group")
                if value and value not in ("Default",):
                    primary_group_value = value
                elif primary_group_value is None:
                    primary_group_value = value or "__any__"
            elif action == "submit":
                do_submit = True
            else:
                extra_actions.append(action_def)

        for action_def in extra_actions:
            planned.append(
                PlannedStep(
                    seq=seq,
                    name=action_def["name"],
                    action=action_def["action"],
                    params=action_def["params"],
                )
            )
            plan_steps.append(
                ExecutionPlanStep(
                    action=action_def["action"],
                    description=action_def["name"],
                    value=action_def["params"].get("value"),
                )
            )
            seq += 1

        if saw_primary_group_flow and primary_group_value is None:
            primary_group_value = "__any__"

        if open_details:
            planned.append(
                PlannedStep(
                    seq=seq,
                    name="Open Customer Details",
                    action="open_customer_details",
                    params={},
                )
            )
            plan_steps.append(
                ExecutionPlanStep(
                    action="open_customer_details",
                    description="Open Customer Details",
                )
            )
            seq += 1

        if primary_group_value is not None:
            planned.append(
                PlannedStep(
                    seq=seq,
                    name=f"Update Primary Group = {primary_group_value}",
                    action="modify_primary_group",
                    params={"primary_group": primary_group_value},
                )
            )
            plan_steps.append(
                ExecutionPlanStep(
                    action="modify_primary_group",
                    description=f"Update Primary Group = {primary_group_value}",
                    value=primary_group_value,
                )
            )
            seq += 1

        if do_submit:
            planned.append(
                PlannedStep(seq=seq, name="Submit", action="submit", params={})
            )
            plan_steps.append(
                ExecutionPlanStep(action="submit", description="Submit")
            )
            seq += 1

        for expected in expected_results:
            planned.append(
                PlannedStep(
                    seq=seq,
                    name=f"Validate: {expected}",
                    action="validate_expected",
                    params={"expected": expected},
                )
            )
            plan_steps.append(
                ExecutionPlanStep(
                    action="validate_expected",
                    description=f"Validate: {expected}",
                    expected=expected,
                )
            )
            seq += 1

        plan = ExecutionPlan(
            scenario_name=self.strategy.template_name,
            objective=f"Workflow {self.strategy.template_key}",
            steps=plan_steps,
            acceptance_checks=expected_results,
        )
        return planned, plan

    def _normalize_business_action(self, raw: dict) -> dict | None:
        if isinstance(raw, str):
            raw = {"description": raw}

        action_name = raw.get("action") or ""
        desc = raw.get("description") or action_name or ""
        value = raw.get("value")
        field = raw.get("field")

        action_key = re.sub(r"[^\w\s]", " ", (action_name or desc)).lower().strip()
        action_key = re.sub(r"\s+", " ", action_key)
        if "=" in action_key and not value:
            action_key, value = [p.strip() for p in action_key.split("=", 1)]

        for pattern in MICRO_STEP_PATTERNS:
            if pattern.search(action_key):
                return None

        mapped = ACTION_MAP.get(action_key)
        if not mapped:
            mapped = self._infer_action(action_key)
        if not mapped:
            normalized = action_key.replace(" ", "_")
            mapped = BUSINESS_ACTION_ALIASES.get(normalized, normalized)

        if mapped not in EXECUTOR_ACTIONS:
            return None

        params: dict = {}
        if mapped == "modify_primary_group":
            params["primary_group"] = value or "__any__"
            params["field"] = field or "Primary Group"
            name = f"Update Primary Group = {params['primary_group']}"
        elif mapped == "open_customer_details":
            name = "Open Customer Details"
        elif mapped == "submit":
            name = "Submit"
        elif mapped == "save_draft":
            name = "Save Draft"
        else:
            name = desc or action_name
            if value:
                params["value"] = value
            if field:
                params["field"] = field

        return {"action": mapped, "name": name, "params": params}

    @staticmethod
    def _infer_action(action_key: str) -> str | None:
        if "customer" in action_key and "detail" in action_key:
            return "open_customer_details"
        if "primary" in action_key and "group" in action_key:
            return "modify_primary_group"
        if ("select" in action_key or "update" in action_key) and "dropdown" in action_key:
            return "modify_primary_group"
        if action_key.endswith("submit") or "click submit" in action_key:
            return "submit"
        return None
