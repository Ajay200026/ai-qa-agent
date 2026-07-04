import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.executor_agent import executor_node
from app.agents.planner_agent import planner_node
from app.agents.report_agent import report_node
from app.agents.scenario_parser_agent import scenario_parser_node
from app.agents.test_understanding_agent import understand_test_pack
from app.agents.validation_agent import validation_node
from app.automation.browser import browser_manager
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import BadRequestError, NotFoundError
from app.events.manager import event_manager
from app.knowledge.knowledge_writer import KnowledgeWriter
from app.knowledge.neo4j_client import neo4j_client
from app.models.execution import Execution, ExecutionStatus, ExecutionStep, StepStatus
from app.models.report import Report
from app.repositories.execution_repository import ExecutionRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.schemas.execution import ExecutionCreate
from app.services.account_query_service import AccountQueryService
from app.services.artifact_service import artifact_basename
from app.services.credential_resolver import CredentialResolver
from app.services.execution_registry import ExecutionCancelled, execution_registry
from app.services.login_as_profile_service import LoginAsProfileService
from app.services.login_resolver import reset_execution_cache
from app.services.salesforce_service import SalesforceService
from app.services.test_case_runner import TestCaseRunner
from app.workflows.test_table_parser import is_test_pack

logger = logging.getLogger(__name__)

# Must re-run in every fresh browser even when DB marks them passed (re-run / resume).
SESSION_BOOTSTRAP_ACTIONS = frozenset({"login", "login_as"})


def _past_session_bootstrap(planned_steps, index: int) -> bool:
    bootstrap_indices = [
        i for i, s in enumerate(planned_steps) if s.action in SESSION_BOOTSTRAP_ACTIONS
    ]
    if not bootstrap_indices:
        return index > 0
    return index > max(bootstrap_indices)


async def _resolve_account_query_if_needed(
    *,
    state: dict,
    planned_steps: list,
    page,
    org,
    db,
    execution_id: UUID,
) -> None:
    if state.get("_account_query_resolved"):
        return
    account_query = state.get("account_query")
    if not account_query or not account_query.get("soql_text"):
        return

    from app.automation.scenario_params import patch_steps_with_resolved_account
    from app.services.account_query_resolver import resolve_account_query

    resolved = await resolve_account_query(
        org,
        state.get("org_credentials", {}),
        page,
        account_query,
        db=db,
    )
    patched = patch_steps_with_resolved_account(
        planned_steps,
        resolved,
        soql_text=account_query["soql_text"],
    )
    planned_steps[:] = patched
    state["planned_steps"] = patched
    state["resolved_account"] = resolved.to_dict()
    state["_account_query_resolved"] = True
    await db.commit()

    await event_manager.emit(
        execution_id,
        "phase_completed",
        step_name="Resolve Account Query",
        status="passed",
        message=(
            f"Using account {resolved.search_number()} "
            f"(index {resolved.pick_index + 1}/{resolved.total_records}), "
            f"sales office {resolved.sales_office or 'n/a'}"
        ),
    )


async def _hydrate_library_state(db: AsyncSession, scenario) -> dict:
    """Load account query and login-as profile snapshots into execution state."""
    extra: dict = {}
    if scenario.account_query_id:
        try:
            aq = await AccountQueryService(db).get(scenario.account_query_id)
            extra["account_query"] = {
                "id": str(aq.id),
                "name": aq.name,
                "soql_text": aq.soql_text,
                "match_hints": aq.match_hints,
            }
        except Exception as exc:
            logger.warning("Could not load account_query %s: %s", scenario.account_query_id, exc)
    if scenario.login_as_profile_id:
        try:
            profile = await LoginAsProfileService(db).get(scenario.login_as_profile_id)
            extra["login_as_profile"] = {
                "id": str(profile.id),
                "name": profile.name,
                "bottler_id": profile.bottler_id,
                "onboarding_role": profile.onboarding_role,
                "enabled": profile.enabled,
                "match_hints": profile.match_hints,
            }
        except Exception as exc:
            logger.warning(
                "Could not load login_as_profile %s: %s", scenario.login_as_profile_id, exc
            )
    return extra


class ExecutionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ExecutionRepository(db)
        self.scenario_repo = ScenarioRepository(db)
        self.sf_service = SalesforceService(db)
        self.settings = get_settings()

    async def create_execution(self, data: ExecutionCreate) -> Execution:
        scenario = await self.scenario_repo.get_by_id(data.scenario_id)
        if not scenario:
            raise NotFoundError("Scenario", data.scenario_id)

        org = await self.sf_service.get_org(data.org_id)

        execution = Execution(
            scenario_id=data.scenario_id,
            org_id=data.org_id,
            status=ExecutionStatus.QUEUED,
        )
        execution = await self.repo.create(execution)
        return execution

    async def get_execution(self, execution_id: UUID) -> Execution:
        execution = await self.repo.get_with_steps(execution_id)
        if not execution:
            raise NotFoundError("Execution", execution_id)
        return execution

    async def list_recent(self, limit: int = 20) -> list[Execution]:
        return await self.repo.list_recent(limit)

    async def list_failed(self, limit: int = 10) -> list[Execution]:
        return await self.repo.list_failed(limit)

    async def delete_execution(self, execution_id: UUID) -> None:
        execution = await self.repo.get_with_steps(execution_id)
        if not execution:
            raise NotFoundError("Execution", execution_id)
        if execution.status in {ExecutionStatus.RUNNING, ExecutionStatus.QUEUED}:
            raise BadRequestError("Cannot delete an active execution")
        await self._remove_artifacts(execution_id)
        await self.repo.delete_execution(execution_id)

    async def clear_failed_executions(self) -> int:
        statuses = [ExecutionStatus.FAILED, ExecutionStatus.ERROR]
        execution_ids = await self._list_ids_by_statuses(statuses)
        for execution_id in execution_ids:
            await self._remove_artifacts(execution_id)
        return await self.repo.clear_by_statuses(statuses)

    async def clear_execution_history(self) -> int:
        statuses = [
            ExecutionStatus.PASSED,
            ExecutionStatus.FAILED,
            ExecutionStatus.ERROR,
            ExecutionStatus.CANCELLED,
        ]
        execution_ids = await self._list_ids_by_statuses(statuses)
        for execution_id in execution_ids:
            await self._remove_artifacts(execution_id)
        return await self.repo.clear_by_statuses(statuses)

    async def _list_ids_by_statuses(self, statuses: list[str]) -> list[UUID]:
        from sqlalchemy import select

        result = await self.db.execute(
            select(Execution.id).where(Execution.status.in_(statuses))
        )
        return [row[0] for row in result.all()]

    async def _remove_artifacts(self, execution_id: UUID) -> None:
        import shutil

        artifacts_dir = self.settings.artifacts_dir / str(execution_id)
        if artifacts_dir.exists():
            shutil.rmtree(artifacts_dir, ignore_errors=True)

    async def rerun_execution(
        self, execution_id: UUID, *, from_step_seq: int | None = None
    ) -> Execution:
        execution = await self.repo.get_with_steps(execution_id)
        if not execution:
            raise NotFoundError("Execution", execution_id)
        if execution.status == ExecutionStatus.RUNNING:
            raise BadRequestError("Cannot rerun while execution is running")
        execution_registry.clear_cancel(execution_id)
        return await self.repo.reset_for_rerun(execution, from_seq=from_step_seq)

    async def update_step_params(
        self, execution_id: UUID, seq: int, params: dict
    ) -> ExecutionStep:
        execution = await self.repo.get_with_steps(execution_id)
        if not execution:
            raise NotFoundError("Execution", execution_id)
        if execution.status not in {
            ExecutionStatus.FAILED,
            ExecutionStatus.ERROR,
            ExecutionStatus.CANCELLED,
        }:
            raise BadRequestError(
                "Can only edit steps for failed, errored, or cancelled executions"
            )
        step = await self.repo.get_step(execution_id, seq)
        if not step:
            raise NotFoundError("ExecutionStep", seq)
        return await self.repo.set_step_params(step, params)

    async def update_step_notes(
        self, execution_id: UUID, seq: int, notes: str | None
    ) -> ExecutionStep:
        execution = await self.repo.get_with_steps(execution_id)
        if not execution:
            raise NotFoundError("Execution", execution_id)
        step = await self.repo.get_step(execution_id, seq)
        if not step:
            raise NotFoundError("ExecutionStep", seq)
        return await self.repo.set_step_notes(step, notes)

    async def stop_execution(self, execution_id: UUID) -> Execution:
        execution = await self.repo.get_with_steps(execution_id)
        if not execution:
            raise NotFoundError("Execution", execution_id)
        if execution.status in {
            ExecutionStatus.PASSED,
            ExecutionStatus.FAILED,
            ExecutionStatus.ERROR,
            ExecutionStatus.CANCELLED,
        }:
            raise BadRequestError("Execution is not active")

        execution_registry.request_cancel(execution_id)
        execution_registry.cancel_task(execution_id)
        await execution_registry.close_context(execution_id)

        if execution.status in {ExecutionStatus.QUEUED, ExecutionStatus.RUNNING}:
            await self._finalize_cancelled(
                self.repo,
                execution,
                started_at=execution.started_at,
            )
            await self.db.commit()

        return execution

    async def run_execution(self, execution_id: UUID) -> None:
        logger.info("Starting execution run for %s", execution_id)
        execution_registry.clear_cancel(execution_id)
        async with AsyncSessionLocal() as db:
            repo = ExecutionRepository(db)
            scenario_repo = ScenarioRepository(db)
            sf_service = SalesforceService(db)

            execution = None
            for attempt in range(5):
                execution = await repo.get_with_steps(execution_id)
                if execution:
                    break
                await asyncio.sleep(0.3 * (attempt + 1))

            if not execution:
                logger.error("Execution %s not found after retries", execution_id)
                await event_manager.emit(
                    execution_id,
                    "execution_error",
                    status="error",
                    message="Execution record not found. Please try again.",
                )
                return

            if execution_registry.is_cancelled(execution_id):
                await self._finalize_cancelled(repo, execution, started_at=None)
                await db.commit()
                return

            scenario = await scenario_repo.get_by_id(execution.scenario_id)
            org = await sf_service.get_org(execution.org_id)
            credentials = sf_service.get_decrypted_credentials(org)

            artifacts_dir = self.settings.artifacts_dir / str(execution_id)
            artifacts_dir.mkdir(parents=True, exist_ok=True)

            started_at = datetime.now(UTC)
            await repo.update_status(
                execution, ExecutionStatus.RUNNING, started_at=started_at
            )
            await db.commit()

            await event_manager.emit(
                execution_id, "execution_started", status="running", message="Execution started"
            )

            test_case_content = self._read_file(scenario.test_case_file, max_chars=50000)
            test_pack_content = scenario.test_pack_content or test_case_content
            if test_pack_content == "N/A":
                test_pack_content = ""

            library_state = await _hydrate_library_state(db, scenario)

            state: dict = {
                "execution_id": execution_id,
                "scenario_name": scenario.name,
                "scenario_description": scenario.description,
                "acceptance_criteria": scenario.acceptance_criteria,
                "test_case_content": test_case_content,
                "test_pack_content": test_pack_content,
                "regression_content": self._read_file(scenario.regression_file),
                "template_key": scenario.template_key,
                "inputs": scenario.inputs or {},
                "business_actions": scenario.business_actions or [],
                "expected_results": scenario.expected_results or [],
                "customer_target": scenario.customer_target or None,
                "login_as_target": scenario.login_as_target or None,
                "identity_map": scenario.identity_map or None,
                "account_query_id": scenario.account_query_id,
                "login_as_profile_id": scenario.login_as_profile_id,
                "org_id": org.id,
                "org_credentials": credentials,
                "login_url": org.login_url,
                "auth_method": org.auth_method,
                "instance_url": org.instance_url,
                "artifacts_dir": str(artifacts_dir),
                **library_state,
            }

            try:
                execution_registry.check_cancelled(execution_id)

                if test_pack_content and is_test_pack(test_pack_content):
                    await self._run_test_pack_execution(
                        execution_id=execution_id,
                        state=state,
                        scenario=scenario,
                        org=org,
                        credentials=credentials,
                        repo=repo,
                        execution=execution,
                        started_at=started_at,
                        artifacts_dir=artifacts_dir,
                    )
                else:
                    await self._run_single_scenario_execution(
                        execution_id=execution_id,
                        state=state,
                        repo=repo,
                        execution=execution,
                        scenario=scenario,
                        org=org,
                        started_at=started_at,
                    )

            except ExecutionCancelled:
                logger.info("Execution %s cancelled by user", execution_id)
                await self._finalize_cancelled(repo, execution, started_at=started_at)
                await db.commit()
            except Exception as exc:
                if execution_registry.is_cancelled(execution_id):
                    logger.info("Execution %s cancelled (browser closed)", execution_id)
                    await self._finalize_cancelled(repo, execution, started_at=started_at)
                    await db.commit()
                else:
                    logger.exception("Execution %s failed: %s", execution_id, exc)
                    await repo.update_status(
                        execution,
                        ExecutionStatus.ERROR,
                        finished_at=datetime.now(UTC),
                    )
                    await db.commit()
                    await event_manager.emit(
                        execution_id, "execution_error", status="error", message=str(exc)
                    )
                    event_manager.clear_buffer(execution_id)
            finally:
                execution_registry.clear_cancel(execution_id)

    async def _run_single_scenario_execution(
        self,
        *,
        execution_id: UUID,
        state: dict,
        repo: ExecutionRepository,
        execution: Execution,
        scenario,
        org,
        started_at: datetime,
    ) -> None:
        parse_result = await scenario_parser_node(state)
        state.update(parse_result)
        await event_manager.emit(
            execution_id, "phase_completed", step_name="Parse Scenario", status="passed"
        )

        execution_registry.check_cancelled(execution_id)
        plan_result = await planner_node(state)
        state.update(plan_result)
        planned_steps = state["planned_steps"]
        state["continue_on_failure"] = False

        # Carry over any user-edited step params from a prior failed run.
        from sqlalchemy import select

        prior_step_rows = await repo.db.execute(
            select(ExecutionStep)
            .where(ExecutionStep.execution_id == execution_id)
        )
        prior_steps_by_seq = {s.seq: s for s in prior_step_rows.scalars().all()}

        for step in planned_steps:
            existing = prior_steps_by_seq.get(step.seq)
            if existing and existing.action_params:
                step.params = {**step.params, **existing.action_params}
            if existing:
                continue
            db_step = ExecutionStep(
                execution_id=execution_id,
                seq=step.seq,
                name=step.name,
                action=step.action,
                status=StepStatus.PENDING,
            )
            await repo.create_step(db_step)
        await repo.update_status(
            execution,
            ExecutionStatus.RUNNING,
            plan_json=state.get("plan").model_dump() if state.get("plan") else None,
        )
        await repo.db.commit()

        execution = await repo.get_with_steps(execution_id)
        if not execution:
            raise RuntimeError("Execution disappeared after planning")

        await event_manager.emit(
            execution_id, "phase_completed", step_name="Plan Steps", status="passed",
            message=f"Planned {len(planned_steps)} steps",
        )

        async def on_event(**kwargs):
            await event_manager.emit(execution_id, **kwargs)

        await event_manager.emit(
            execution_id,
            "phase_completed",
            step_name="Launch Salesforce",
            status="running",
            message="Opening browser and logging into Salesforce...",
        )

        artifacts_dir = Path(state["artifacts_dir"])
        logger.info("Launching Playwright browser for execution %s", execution_id)
        await browser_manager.start()
        async with browser_manager.new_context(execution_id) as (_context, page):
            reset_execution_cache(execution_id)
            active_page: list = [page]

            # If any DB steps are already passed (re-run from a later step), skip them.
            passed_seqs = {
                s.seq for s in execution.steps if s.status == StepStatus.PASSED
            }
            start_index = 0
            for i, ps in enumerate(planned_steps):
                if ps.seq not in passed_seqs:
                    start_index = i
                    break
            else:
                start_index = len(planned_steps)
            state["current_step_index"] = start_index
            state["step_results"] = []
            state["max_retries"] = 2

            async def _run_step_at(index: int) -> None:
                state["current_step_index"] = index
                current_step = planned_steps[index]
                db_step = next(
                    (s for s in execution.steps if s.seq == current_step.seq), None
                )
                if db_step:
                    await repo.update_step(
                        db_step, status=StepStatus.RUNNING, started_at=datetime.now(UTC)
                    )
                    await repo.db.commit()
                exec_result = await executor_node(state, active_page[0], on_event)
                if exec_result.get("active_page"):
                    active_page[0] = exec_result["active_page"]
                state.update(exec_result)
                if state.get("step_results"):
                    latest = state["step_results"][-1]
                    if db_step:
                        await repo.update_step(
                            db_step,
                            status=latest.status,
                            screenshot_path=artifact_basename(latest.screenshot_path),
                            error=latest.error,
                            finished_at=datetime.now(UTC),
                        )
                        await repo.db.commit()
                if state.get("error"):
                    raise RuntimeError(state["error"])

            # Fresh browser has no session — always establish OAuth login + Login As first.
            bootstrap_done = False
            if start_index > 0:
                for i, ps in enumerate(planned_steps):
                    if ps.action in SESSION_BOOTSTRAP_ACTIONS:
                        await _run_step_at(i)
                bootstrap_done = True
                state["step_results"] = []
                state["error"] = None
                await _resolve_account_query_if_needed(
                    state=state,
                    planned_steps=planned_steps,
                    page=active_page[0],
                    org=org,
                    db=repo.db,
                    execution_id=execution_id,
                )

            state["current_step_index"] = start_index

            while state["current_step_index"] < len(planned_steps):
                execution_registry.check_cancelled(execution_id)
                if _past_session_bootstrap(
                    planned_steps, state["current_step_index"]
                ):
                    await _resolve_account_query_if_needed(
                        state=state,
                        planned_steps=planned_steps,
                        page=active_page[0],
                        org=org,
                        db=repo.db,
                        execution_id=execution_id,
                    )
                step = planned_steps[state["current_step_index"]]
                if bootstrap_done and step.action in SESSION_BOOTSTRAP_ACTIONS:
                    state["current_step_index"] += 1
                    continue
                try:
                    await _run_step_at(state["current_step_index"])
                except RuntimeError:
                    break
                if state.get("error"):
                    break

            await event_manager.emit(
                execution_id, "phase_completed", step_name="Execute Scenario", status="passed"
            )

            validation_result = await validation_node(state, active_page[0])
            state.update(validation_result)
            await event_manager.emit(
                execution_id,
                "phase_completed",
                step_name="Validation",
                status="passed" if state["validation"].passed else "failed",
            )

        await self._finalize_execution_report(
            execution_id=execution_id,
            state=state,
            repo=repo,
            execution=execution,
            scenario=scenario,
            started_at=started_at,
            artifacts_dir=artifacts_dir,
            planned_steps=planned_steps,
        )

    async def _run_test_pack_execution(
        self,
        *,
        execution_id: UUID,
        state: dict,
        scenario,
        org,
        credentials: dict,
        repo: ExecutionRepository,
        execution: Execution,
        started_at: datetime,
        artifacts_dir: Path,
    ) -> None:
        await event_manager.emit(
            execution_id, "phase_completed", step_name="Understand Test Pack", status="running"
        )
        pack = await understand_test_pack(state.get("test_pack_content", ""))
        state["test_pack"] = pack
        state["is_test_pack_run"] = True

        await event_manager.emit(
            execution_id,
            "phase_completed",
            step_name="Understand Test Pack",
            status="passed",
            message=f"Parsed {len(pack.test_cases)} test cases",
        )

        org_map: dict[str, UUID] = {"default": org.id}
        if org.role or org.bottler:
            key = CredentialResolver._identity_key(org.role, org.bottler)
            org_map[key] = org.id

        resolver = CredentialResolver(repo.db, org.id)

        seq = 1
        for tc in pack.test_cases:
            for step in tc.steps:
                db_step = ExecutionStep(
                    execution_id=execution_id,
                    seq=seq,
                    name=f"{tc.tc_id}: {step.description or step.action}",
                    action=step.action,
                    status=StepStatus.PENDING,
                )
                await repo.create_step(db_step)
                seq += 1

        await repo.update_status(
            execution,
            ExecutionStatus.RUNNING,
            plan_json={"test_pack": pack.model_dump(), "mode": "test_pack"},
        )
        await repo.db.commit()

        async def on_event(**kwargs):
            await event_manager.emit(execution_id, **kwargs)

        await event_manager.emit(
            execution_id,
            "phase_completed",
            step_name="Launch Salesforce",
            status="running",
            message="Opening browser for test pack execution...",
        )

        await browser_manager.start()
        profile_rows = await LoginAsProfileService(repo.db).list_by_project(scenario.project_id)
        async with browser_manager.new_context(execution_id) as (_context, page):
            runner = TestCaseRunner(
                page=page,
                artifacts_dir=artifacts_dir,
                execution_id=execution_id,
                credential_resolver=resolver,
                org_map=org_map,
                template_key=state.get("template_key") or "DATA_CHANGE_REQUEST",
                continue_on_failure=True,
                org=org,
                admin_credentials=credentials,
                login_url=org.login_url,
                auth_method=org.auth_method,
                instance_url=org.instance_url,
                login_as_target=state.get("login_as_target"),
                identity_map=state.get("identity_map"),
                login_as_profile=state.get("login_as_profile"),
                login_as_profiles=[
                    {
                        "id": str(p.id),
                        "name": p.name,
                        "bottler_id": p.bottler_id,
                        "onboarding_role": p.onboarding_role,
                        "enabled": p.enabled,
                        "match_hints": p.match_hints,
                    }
                    for p in profile_rows
                ],
                account_query=state.get("account_query"),
                test_pack_text=state.get("test_pack_content") or "",
            )
            pack_result = await runner.run_pack(pack, page=page, on_event=on_event)
            state["test_pack_result"] = pack_result
            state["trace_events"] = runner.trace_events

        state["validation"] = None
        report_result = await report_node(state)
        state.update(report_result)
        report_data = state["report"]

        finished_at = datetime.now(UTC)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        final_status = ExecutionStatus.PASSED if report_data.passed else ExecutionStatus.FAILED

        await repo.update_status(
            execution,
            final_status,
            finished_at=finished_at,
            duration_ms=duration_ms,
            plan_json={
                "test_pack": pack.model_dump(),
                "test_pack_result": pack_result.model_dump(),
                "trace_events": runner.trace_events,
            },
        )

        report = Report(
            execution_id=execution_id,
            summary=report_data.summary,
            passed_count=report_data.passed_count,
            failed_count=report_data.failed_count,
            llm_analysis=report_data.llm_analysis,
            artifacts_path=str(artifacts_dir),
        )
        repo.db.add(report)
        await repo.db.commit()

        await event_manager.emit(
            execution_id,
            "execution_completed",
            status=final_status,
            message=report_data.summary[:500],
        )
        event_manager.clear_buffer(execution_id)

    async def _finalize_execution_report(
        self,
        *,
        execution_id: UUID,
        state: dict,
        repo: ExecutionRepository,
        execution: Execution,
        scenario,
        started_at: datetime,
        artifacts_dir: Path,
        planned_steps,
    ) -> None:
        report_result = await report_node(state)
        state.update(report_result)
        report_data = state["report"]

        finished_at = datetime.now(UTC)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        final_status = ExecutionStatus.PASSED if report_data.passed else ExecutionStatus.FAILED

        await repo.update_status(
            execution,
            final_status,
            finished_at=finished_at,
            duration_ms=duration_ms,
        )

        report = Report(
            execution_id=execution_id,
            summary=report_data.summary,
            passed_count=report_data.passed_count,
            failed_count=report_data.failed_count,
            llm_analysis=report_data.llm_analysis,
            artifacts_path=str(artifacts_dir),
        )
        repo.db.add(report)
        await repo.db.commit()

        try:
            writer = KnowledgeWriter(neo4j_client)
            await writer.store_execution(
                scenario_id=scenario.id,
                scenario_name=scenario.name,
                execution_id=execution_id,
                report=report_data,
                planned_steps=planned_steps,
                step_results=state.get("step_results", []),
            )
        except Exception as exc:
            logger.warning("Failed to store Neo4j knowledge: %s", exc)

        if not report_data.passed:
            try:
                from app.agents.rca_agent import run_rca_analysis

                rca = await run_rca_analysis(
                    str(scenario.id),
                    scenario.name,
                    report_data,
                    state.get("step_results", []),
                    str(execution_id),
                )
                if rca:
                    report.rca_analysis = rca.model_dump()
                    await repo.db.commit()
            except Exception as exc:
                logger.warning("RCA analysis failed: %s", exc)

        await event_manager.emit(
            execution_id,
            "execution_completed",
            status=final_status,
            message=report_data.summary[:500],
        )
        event_manager.clear_buffer(execution_id)

    async def _finalize_cancelled(
        self,
        repo: ExecutionRepository,
        execution: Execution,
        *,
        started_at: datetime | None,
    ) -> None:
        if execution.status == ExecutionStatus.CANCELLED:
            return

        finished_at = datetime.now(UTC)
        duration_ms = None
        if started_at:
            duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        for step in execution.steps or []:
            if step.status in {StepStatus.PENDING, StepStatus.RUNNING}:
                await repo.update_step(
                    step,
                    status=StepStatus.SKIPPED,
                    error="Stopped by user",
                    finished_at=finished_at,
                )

        await repo.update_status(
            execution,
            ExecutionStatus.CANCELLED,
            finished_at=finished_at,
            duration_ms=duration_ms,
        )
        await event_manager.emit(
            execution.id,
            "execution_cancelled",
            status="cancelled",
            message="Execution stopped by user",
        )
        event_manager.clear_buffer(execution.id)

    def _read_file(self, path: str | None, *, max_chars: int = 5000) -> str:
        if not path:
            return "N/A"
        try:
            return Path(path).read_text(encoding="utf-8", errors="ignore")[:max_chars]
        except Exception:
            return "N/A"


async def run_execution_background(execution_id: UUID) -> None:
    """Standalone entry point for background tasks (uses its own DB session)."""
    try:
        async with AsyncSessionLocal() as db:
            service = ExecutionService(db)
            await service.run_execution(execution_id)
    except asyncio.CancelledError:
        logger.info("Background task for execution %s was cancelled", execution_id)
        raise
    except ExecutionCancelled:
        logger.info("Execution %s stopped", execution_id)
    except Exception as exc:
        if execution_registry.is_cancelled(execution_id):
            logger.info("Execution %s stopped during error handling", execution_id)
            return
        logger.exception("Background execution %s crashed: %s", execution_id, exc)
        await event_manager.emit(
            execution_id,
            "execution_error",
            status="error",
            message=str(exc),
        )
        try:
            async with AsyncSessionLocal() as db:
                repo = ExecutionRepository(db)
                execution = await repo.get_with_steps(execution_id)
                if execution and execution.status in {
                    ExecutionStatus.QUEUED,
                    ExecutionStatus.RUNNING,
                }:
                    await repo.update_status(
                        execution,
                        ExecutionStatus.ERROR,
                        finished_at=datetime.now(UTC),
                    )
                    await db.commit()
        except Exception as mark_exc:
            logger.warning(
                "Failed to mark execution %s as error after crash: %s",
                execution_id,
                mark_exc,
            )
        event_manager.clear_buffer(execution_id)
    finally:
        execution_registry.unregister_task(execution_id)


def schedule_execution_run(execution_id: UUID) -> None:
    """Schedule execution on the running event loop (more reliable than BackgroundTasks)."""
    task = asyncio.create_task(run_execution_background(execution_id))
    execution_registry.register_task(execution_id, task)
