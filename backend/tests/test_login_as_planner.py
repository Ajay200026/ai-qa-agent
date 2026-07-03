"""Planner login_as splice tests."""

from app.automation.scenario_params import apply_account_query_to_steps, splice_login_as_step
from app.schemas.agent import PlannedStep


def _base_steps() -> list[PlannedStep]:
    return [
        PlannedStep(seq=1, name="Login", action="login", params={}),
        PlannedStep(seq=2, name="Open Queues", action="open_queues", params={}),
    ]


def test_splices_login_as_when_configured():
    state = {
        "login_as_target": {
            "bottler_id": "5000",
            "onboarding_role": "Requestor",
            "enabled": True,
        }
    }
    steps = splice_login_as_step(_base_steps(), state)
    actions = [s.action for s in steps]
    assert actions == ["login", "login_as", "open_queues"]
    login_as = steps[1]
    assert login_as.params["bottler_id"] == "5000"
    assert login_as.params["onboarding_role"] == "Requestor"
    assert steps[0].seq == 1 and steps[1].seq == 2 and steps[2].seq == 3


def test_omits_login_as_when_disabled():
    state = {
        "login_as_target": {
            "bottler_id": "5000",
            "onboarding_role": "Requestor",
            "enabled": False,
        }
    }
    steps = splice_login_as_step(_base_steps(), state)
    assert [s.action for s in steps] == ["login", "open_queues"]


def test_idempotent_when_login_as_already_present():
    state = {
        "login_as_target": {
            "bottler_id": "5000",
            "onboarding_role": "Requestor",
            "enabled": True,
        }
    }
    steps = _base_steps() + [
        PlannedStep(seq=3, name="Login as", action="login_as", params={}),
    ]
    result = splice_login_as_step(steps, state)
    assert sum(1 for s in result if s.action == "login_as") == 1


def test_apply_account_query_replaces_load_customer():
    steps = [
        PlannedStep(seq=1, name="Login", action="login", params={}),
        PlannedStep(seq=2, name="Load", action="load_customer", params={"customer_number": "1"}),
    ]
    state = {
        "account_query": {
            "name": "AR",
            "soql_text": "SELECT Id FROM Account LIMIT 1",
            "match_hints": {},
        }
    }
    result = apply_account_query_to_steps(steps, state)
    assert result[1].action == "load_customer_by_query"
    assert "soql_text" in result[1].params
