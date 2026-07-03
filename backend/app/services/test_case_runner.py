"""Run a TestPack: per-TC execution with assertions and state isolation."""

from __future__ import annotations

import logging
import time
from types import SimpleNamespace
from typing import Any, Awaitable, Callable
from uuid import UUID

from playwright.async_api import Page

from app.agents.executor_agent import StepExecutor
from app.automation.assertions import run_assertion
from app.schemas.agent import PlannedStep, StepResult
from app.schemas.login_as import LoginAsTarget
from app.schemas.test_case import (
    AssertionEvidence,
    TestCase,
    TestCaseResult,
    TestPack,
    TestPackResult,
    TestStepResult,
)
from app.services.credential_resolver import CredentialResolver
from app.services.identity_selector import resolve_identity
from app.services.login_resolver import reset_execution_cache
from app.services.recommendation_service import resolve_profile_dict_for_tc
from app.services.tracing import ExecutionTracer
from app.workflows.test_pack_planner import (
    NAVIGATION_STEPS,
    baseline_reset_steps,
    planned_steps_for_test_case,
    smoke_test_cases,
)

logger = logging.getLogger(__name__)

EventCallback = Callable[..., Awaitable[None]]


class TestCaseRunner:
    def __init__(
        self,
        page: Page,
        artifacts_dir,
        execution_id: UUID,
        credential_resolver: CredentialResolver,
        *,
        org_map: dict[str, UUID] | None = None,
        template_key: str = "DATA_CHANGE_REQUEST",
        db=None,
        continue_on_failure: bool = True,
        org=None,
        admin_credentials: dict | None = None,
        login_url: str | None = None,
        auth_method: str | None = None,
        instance_url: str | None = None,
        login_as_target: dict | LoginAsTarget | None = None,
        identity_map: dict | None = None,
        login_as_profile: dict | None = None,
        login_as_profiles: list[dict] | None = None,
        account_query: dict | None = None,
        test_pack_text: str = "",
    ):
        self.page = page
        self.artifacts_dir = artifacts_dir
        self.execution_id = execution_id
        self.credential_resolver = credential_resolver
        self.org_map = org_map or {}
        self.template_key = template_key
        self.db = db
        self.continue_on_failure = continue_on_failure
        self.tracer = ExecutionTracer()
        self.org = org
        self.admin_credentials = admin_credentials or {}
        self.login_url = login_url or ""
        self.auth_method = auth_method or "credentials"
        self.instance_url = instance_url
        self.login_as_target = login_as_target
        self.identity_map = identity_map
        self.login_as_profile = login_as_profile
        self.login_as_profiles = login_as_profiles or []
        self.account_query = account_query
        self.test_pack_text = test_pack_text
        self._current_impersonation_key: str | None = None
        self._navigated = False
        self.resolved_account = None
        self._account_query_resolved = False

    def _org_shim(self):
        org = self.org
        if org is not None:
            return org
        return SimpleNamespace(
            id=self.execution_id,
            login_url=self.login_url,
            auth_method=self.auth_method,
            instance_url=self.instance_url,
        )

    def _build_executor(self, credentials: dict | None = None) -> StepExecutor:
        creds = credentials if credentials is not None else self.admin_credentials
        return StepExecutor(
            page=self.page,
            artifacts_dir=self.artifacts_dir,
            credentials=creds,
            login_url=self.login_url,
            auth_method=self.auth_method,
            execution_id=self.execution_id,
            template_key=self.template_key,
            db=self.db,
            continue_on_failure=self.continue_on_failure,
            org=self._org_shim(),
            instance_url=self.instance_url,
        )

    async def run_pack(
        self,
        pack: TestPack,
        *,
        page: Page | None = None,
        on_event: EventCallback | None = None,
        smoke_only: bool = False,
    ) -> TestPackResult:
        reset_execution_cache(self.execution_id)
        self._current_impersonation_key = None
        self.resolved_account = None
        self._account_query_resolved = False
        if page is not None:
            self.page = page
        cases = smoke_test_cases(pack) if smoke_only else pack.test_cases
        results: list[TestCaseResult] = []
        smoke_ids = {s.upper().replace("_", "-") for s in pack.smoke_subset}

        for tc in cases:
            if on_event:
                await on_event(
                    event_type="test_case_started",
                    step_name=tc.tc_id,
                    message=f"Running {tc.tc_id}: {tc.title}",
                )
            tc_result = await self.run_test_case(tc, pack_bottler=pack.bottler, on_event=on_event)
            tc_result.is_smoke = tc.tc_id.upper().replace("_", "-") in smoke_ids
            results.append(tc_result)
            if on_event:
                await on_event(
                    event_type="test_case_completed",
                    step_name=tc.tc_id,
                    status=tc_result.status,
                    message=tc_result.error or f"{tc.tc_id} {tc_result.status}",
                )

        passed = sum(1 for r in results if r.status == "passed")
        failed = sum(1 for r in results if r.status == "failed")
        blocked = sum(1 for r in results if r.status == "blocked")
        skipped = sum(1 for r in results if r.status == "skipped")

        return TestPackResult(
            title=pack.title,
            passed_count=passed,
            failed_count=failed,
            blocked_count=blocked,
            skipped_count=skipped,
            test_case_results=results,
            smoke_subset=pack.smoke_subset,
        )

    def _resolve_login_target(
        self, tc: TestCase, pack_bottler: str | None
    ) -> LoginAsTarget | None:
        tc_bottler = tc.bottler or pack_bottler
        if self.login_as_profiles or self.login_as_profile:
            picked = resolve_profile_dict_for_tc(
                self.login_as_profiles,
                tc_bottler=tc_bottler,
                tc_role=tc.role,
                default_profile=self.login_as_profile,
                pack_text=self.test_pack_text,
            )
            if picked:
                return LoginAsTarget(
                    bottler_id=picked["bottler_id"],
                    onboarding_role=picked["onboarding_role"],
                    enabled=picked.get("enabled", True),
                )
            return None
        return resolve_identity(
            tc_bottler=tc_bottler,
            tc_role=tc.role,
            identity_map=self.identity_map,
            default=self.login_as_target,
        )

    def _adapt_step_for_query(self, step: PlannedStep) -> PlannedStep:
        if not self.account_query or step.action != "load_customer":
            return step
        soql = self.account_query.get("soql_text")
        if not soql:
            return step
        hints = self.account_query.get("match_hints") or {}
        return PlannedStep(
            seq=step.seq,
            name=f"Load customer via query: {self.account_query.get('name', 'saved')}",
            action="load_customer_by_query",
            params={
                k: v
                for k, v in {
                    "soql_text": soql,
                    "account_group": hints.get("account_group"),
                    "distribution_channel": hints.get("distribution_channel"),
                    "sales_office": hints.get("sales_office"),
                    **step.params,
                }.items()
                if v
            },
        )

    def _prepare_step(self, step: PlannedStep) -> PlannedStep:
        from app.automation.scenario_params import patch_steps_with_resolved_account

        adapted = self._adapt_step_for_query(step)
        if self.resolved_account and self.account_query:
            soql = self.account_query.get("soql_text") or ""
            return patch_steps_with_resolved_account(
                [adapted], self.resolved_account, soql_text=soql
            )[0]
        return adapted

    async def _ensure_account_resolved(self) -> None:
        if self._account_query_resolved or not self.account_query:
            return
        soql = self.account_query.get("soql_text")
        if not soql:
            return
        from app.services.account_query_resolver import resolve_account_query

        self.resolved_account = await resolve_account_query(
            self._org_shim(),
            self.admin_credentials,
            self.page,
            self.account_query,
            db=self.db,
        )
        self._account_query_resolved = True

    async def run_test_case(
        self,
        tc: TestCase,
        *,
        pack_bottler: str | None = None,
        on_event: EventCallback | None = None,
    ) -> TestCaseResult:
        tc_bottler = tc.bottler or pack_bottler
        target = self._resolve_login_target(tc, pack_bottler)

        try:
            creds, login_url, auth_method, instance_url = await self.credential_resolver.resolve(
                org_map=self.org_map,
            )
        except Exception as exc:
            return TestCaseResult(
                tc_id=tc.tc_id, title=tc.title, status="blocked", error=str(exc),
            )

        if login_url:
            self.login_url = login_url
        if auth_method:
            self.auth_method = auth_method
        if instance_url:
            self.instance_url = instance_url
        self.admin_credentials = creds

        executor = self._build_executor(creds)

        step_results: list[TestStepResult] = []
        tc_failed = False

        try:
            if not self._navigated:
                for nav in NAVIGATION_STEPS:
                    if nav.action == "login_as":
                        continue
                    sr = await self._run_planned_step(executor, nav, tc.tc_id, on_event)
                    step_results.append(sr)
                    if sr.status == "failed":
                        tc_failed = True
                        if not self.continue_on_failure:
                            break
                self._navigated = True

            if not tc_failed or self.continue_on_failure:
                impersonation_failed = await self._ensure_impersonation(
                    executor, target, tc.tc_id, step_results, on_event
                )
                if impersonation_failed:
                    tc_failed = True

            if not tc_failed or self.continue_on_failure:
                await self._ensure_account_resolved()
                for planned in planned_steps_for_test_case(tc):
                    adapted = self._prepare_step(planned)
                    sr = await self._run_planned_step(executor, adapted, tc.tc_id, on_event)
                    step_results.append(sr)
                    if sr.status in ("failed", "blocked"):
                        tc_failed = True
                        if not self.continue_on_failure:
                            break

            if not tc_failed or self.continue_on_failure:
                for reset in baseline_reset_steps():
                    sr = await self._run_planned_step(executor, reset, tc.tc_id, on_event)
                    step_results.append(sr)

        except Exception as exc:
            logger.exception("Test case %s error: %s", tc.tc_id, exc)
            return TestCaseResult(
                tc_id=tc.tc_id,
                title=tc.title,
                status="failed",
                role=tc.role,
                bottler=tc_bottler,
                step_results=step_results,
                error=str(exc),
            )

        status = "failed" if tc_failed else "passed"
        if any(s.status == "blocked" for s in step_results):
            status = "blocked"

        return TestCaseResult(
            tc_id=tc.tc_id,
            title=tc.title,
            status=status,
            role=tc.role,
            bottler=tc_bottler,
            step_results=step_results,
        )

    async def _ensure_impersonation(
        self,
        executor: StepExecutor,
        target: LoginAsTarget | None,
        tc_id: str,
        step_results: list[TestStepResult],
        on_event: EventCallback | None,
    ) -> bool:
        new_key = target.cache_key() if target else None
        if new_key and new_key == self._current_impersonation_key and target:
            resolver = executor._get_login_resolver()
            if await resolver.is_impersonating(
                target.bottler_id, target.onboarding_role
            ):
                return False

        if self._current_impersonation_key and new_key != self._current_impersonation_key:
            relogin = PlannedStep(seq=0, name="Re-login admin", action="login", params={})
            sr = await self._run_planned_step(executor, relogin, tc_id, on_event)
            step_results.append(sr)
            if sr.status == "failed":
                return True

        if target:
            label = f"Impersonate {target.onboarding_role}@{target.bottler_id}"
            if on_event:
                await on_event(
                    event_type="phase_completed",
                    step_name=label,
                    status="running",
                    message=label,
                )
            login_as_step = PlannedStep(
                seq=0,
                name=label,
                action="login_as",
                params={
                    "bottler_id": target.bottler_id,
                    "onboarding_role": target.onboarding_role,
                },
            )
            sr = await self._run_planned_step(executor, login_as_step, tc_id, on_event)
            step_results.append(sr)
            if on_event:
                await on_event(
                    event_type="phase_completed",
                    step_name=label,
                    status=sr.status,
                    message=sr.error or label,
                )
            if sr.status == "failed":
                return True

        self._current_impersonation_key = new_key
        return False

    async def _run_planned_step(
        self,
        executor: StepExecutor,
        step: PlannedStep,
        tc_id: str,
        on_event: EventCallback | None,
    ) -> TestStepResult:
        start = time.perf_counter()
        assertion_results: list[AssertionEvidence] = []

        async with self.tracer.step_span(tc_id, step.seq, step.action):
            result = await executor.execute(step)
            self.page = executor.page

        if result.status == "passed" and step.params.get("assertions"):
            for raw in step.params["assertions"]:
                from app.schemas.test_case import Assertion

                assertion = Assertion(**raw) if isinstance(raw, dict) else raw
                passed, detail, actual = await run_assertion(self.page, assertion, db=self.db)
                evidence = AssertionEvidence(
                    kind=assertion.kind.value,
                    passed=passed,
                    expected=assertion.expected,
                    actual=actual,
                    detail=detail,
                )
                assertion_results.append(evidence)
                self.tracer.record_assertion(tc_id, step.seq, evidence)
                if not passed and not self.continue_on_failure:
                    result = StepResult(
                        seq=result.seq,
                        name=result.name,
                        action=result.action,
                        status="failed",
                        screenshot_path=result.screenshot_path,
                        error=f"Assertion failed: {detail}",
                        logs=result.logs,
                    )

        duration = int((time.perf_counter() - start) * 1000)
        status = result.status
        if assertion_results and any(not a.passed for a in assertion_results):
            status = "failed"

        if on_event:
            await on_event(
                event_type="step_completed",
                step_seq=step.seq,
                step_name=step.name,
                status=status,
                message=result.error or step.name,
                screenshot_path=result.screenshot_path,
            )

        return TestStepResult(
            seq=step.seq,
            action=step.action,
            description=step.name,
            status=status,
            error=result.error,
            screenshot_path=result.screenshot_path,
            assertion_results=assertion_results,
            logs=result.logs,
            duration_ms=duration,
            retry_count=result.logs.count("retry") if result.logs else 0,
        )

    @property
    def trace_events(self) -> list[dict[str, Any]]:
        return self.tracer.events
