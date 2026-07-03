"""TestCaseRunner per-TC identity switching tests."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.schemas.login_as import LoginAsTarget
from app.schemas.test_case import TestCase as TcModel
from app.schemas.test_case import TestPack as PackModel
from app.schemas.test_case import TestStep as StepModel
from app.services.test_case_runner import TestCaseRunner


def _tc(tc_id: str, role: str | None, bottler: str | None = "5000") -> TcModel:
    return TcModel(
        tc_id=tc_id,
        title=tc_id,
        role=role,
        bottler=bottler,
        steps=[
            StepModel(seq=1, description="Set field", action="set_field", params={"field": "x"})
        ],
    )


def _runner() -> TestCaseRunner:
    page = MagicMock()
    resolver = MagicMock()
    resolver.resolve = AsyncMock(
        return_value=(
            {"username": "admin"},
            "https://test.salesforce.com",
            "credentials",
            "https://example.my.salesforce.com",
        )
    )
    return TestCaseRunner(
        page=page,
        artifacts_dir="/tmp",
        execution_id=uuid4(),
        credential_resolver=resolver,
        org=SimpleNamespace(id=uuid4(), instance_url="https://example.my.salesforce.com"),
        admin_credentials={"username": "admin"},
        login_url="https://test.salesforce.com",
        auth_method="credentials",
        instance_url="https://example.my.salesforce.com",
        login_as_target=LoginAsTarget(
            bottler_id="5000", onboarding_role="Requestor", enabled=True
        ),
    )


def test_two_identities_trigger_two_login_as_calls():
    runner = _runner()
    pack = PackModel(
        test_cases=[
            _tc("TC-01", "Requestor"),
            _tc("TC-02", "Requestor"),
            _tc("TC-03", "Finance"),
        ]
    )

    login_as_calls: list[tuple[str, str]] = []

    async def fake_run_planned(executor, step, tc_id, on_event=None):
        from app.schemas.test_case import TestStepResult

        if step.action == "login_as":
            login_as_calls.append(
                (step.params["bottler_id"], step.params["onboarding_role"])
            )
        return TestStepResult(
            seq=step.seq,
            action=step.action,
            description=step.name,
            status="passed",
        )

    with patch.object(runner, "_run_planned_step", side_effect=fake_run_planned):
        runner._navigated = True
        result = asyncio.run(runner.run_pack(pack))

    assert len(login_as_calls) == 2
    assert login_as_calls[0] == ("5000", "Requestor")
    assert login_as_calls[1] == ("5000", "Finance")
    assert result.passed_count == 3