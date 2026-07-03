"""Convert TestCase steps into PlannedStep sequences."""

from __future__ import annotations

from app.schemas.agent import PlannedStep
from app.schemas.test_case import TestCase, TestPack
from app.workflows.action_mapping import expects_request_submission
from app.workflows.merger import EXECUTOR_ACTIONS


NAVIGATION_STEPS: list[PlannedStep] = [
    PlannedStep(seq=1, name="Login", action="login", params={}),
    PlannedStep(seq=2, name="Open Queues", action="open_queues", params={}),
    PlannedStep(seq=3, name="Click New", action="click_new_button", params={"button_label": "New"}),
    PlannedStep(
        seq=4,
        name="Select Request Module",
        action="select_request_module",
        params={"module_option": "NEW DATA CHANGE"},
    ),
]


def _step_needs_submit_first(step: PlannedStep) -> bool:
    if step.action == "validate_expected":
        return expects_request_submission(step.params.get("expected", ""))
    for raw in step.params.get("assertions") or []:
        kind = raw.get("kind") if isinstance(raw, dict) else getattr(raw, "kind", None)
        if kind in ("request_created", "status_submitted"):
            return True
    return False


def planned_steps_for_test_case(tc: TestCase, *, base_seq: int = 100) -> list[PlannedStep]:
    planned: list[PlannedStep] = []
    seq = base_seq
    for step in tc.steps:
        params = dict(step.params)
        if step.target:
            params.setdefault("field", step.target)
        if step.value:
            if step.action == "modify_primary_group":
                params["primary_group"] = step.value
            elif step.action == "change_business_type":
                params["value"] = step.value
            elif step.action == "load_customer":
                params["customer_number"] = step.value
            else:
                params.setdefault("value", step.value)
        if step.assertions:
            params["assertions"] = [a.model_dump() for a in step.assertions]
        params["description"] = step.description
        params["tc_id"] = tc.tc_id

        action = step.action if step.action in EXECUTOR_ACTIONS else "set_field"
        planned_step = PlannedStep(
            seq=seq,
            name=step.description or f"{tc.tc_id} step {step.seq}",
            action=action,
            params=params,
        )
        if (
            _step_needs_submit_first(planned_step)
            and not any(s.action == "submit" for s in planned)
        ):
            planned.append(PlannedStep(seq=seq, name="Submit", action="submit", params={}))
            seq += 1
        planned.append(planned_step)
        seq += 1
    return planned


def baseline_reset_steps(*, base_seq: int = 90) -> list[PlannedStep]:
    return [
        PlannedStep(seq=base_seq, name="Reset: Open Queues", action="open_queues", params={}),
        PlannedStep(
            seq=base_seq + 1,
            name="Reset: New Data Change",
            action="create_data_change_request",
            params={"menu_option": "NEW DATA CHANGE"},
        ),
    ]


def smoke_test_cases(pack: TestPack) -> list[TestCase]:
    if not pack.smoke_subset:
        return pack.test_cases
    ids = {s.upper().replace("_", "-") for s in pack.smoke_subset}
    return [tc for tc in pack.test_cases if tc.tc_id.upper().replace("_", "-") in ids] or pack.test_cases
