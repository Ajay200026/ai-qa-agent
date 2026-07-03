"""Submit step injection and request-created assertion inference."""

from unittest.mock import MagicMock

from app.schemas.agent import PlannedStep
from app.workflows.action_mapping import expects_request_submission, infer_assertions_from_expected
from app.workflows.merger import PlanMerger
from app.workflows.test_pack_planner import planned_steps_for_test_case
from app.schemas.test_case import TestCase, TestStep


def test_expects_request_submission_matches_is_created():
    assert expects_request_submission("Request is created successfully.")
    assert expects_request_submission("Request created successfully")


def test_infer_assertions_request_created_not_text_visible():
    assertions = infer_assertions_from_expected("Request is created successfully.")
    kinds = {a.kind.value for a in assertions}
    assert "request_created" in kinds
    assert "text_visible" not in kinds


def test_merge_injects_submit_before_validation():
    strategy = MagicMock()
    strategy._template_steps = []
    strategy._should_include_step = lambda _step: True
    strategy._substitute_params = lambda params: params
    strategy._inputs = {}
    strategy.template_name = "Data Change"
    strategy.template_key = "DATA_CHANGE_REQUEST"

    merger = PlanMerger(strategy)
    planned, _ = merger.merge(
        [{"description": "Update Primary Group to A0168", "value": "A0168"}],
        ["Request is created successfully."],
    )
    actions = [step.action for step in planned]
    assert "submit" in actions
    assert "validate_expected" in actions
    assert actions.index("submit") < actions.index("validate_expected")


def test_test_pack_planner_injects_submit_before_validate_step():
    tc = TestCase(
        tc_id="TC-DC-001",
        title="Update Primary Group",
        steps=[
            TestStep(
                seq=1,
                action="modify_primary_group",
                description="Update Primary Group to A0168",
                value="A0168",
            ),
            TestStep(
                seq=2,
                action="validate_expected",
                description="Validate success",
                params={"expected": "Request is created successfully."},
            ),
        ],
    )
    planned = planned_steps_for_test_case(tc)
    actions = [step.action for step in planned]
    assert actions == ["modify_primary_group", "submit", "validate_expected"]
