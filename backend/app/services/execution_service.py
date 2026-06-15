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
from app.services.execution_registry import ExecutionCancelled, execution_registry
from app.services.salesforce_service import SalesforceService

logger = logging.getLogger(__name__)


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

    async def rerun_execution(self, execution_id: UUID) -> Execution:
        execution = await self.repo.get_with_steps(execution_id)
        if not execution:
            raise NotFoundError("Execution", execution_id)
        if execution.status == ExecutionStatus.RUNNING:
            raise BadRequestError("Cannot rerun while execution is running")
        execution_registry.clear_cancel(execution_id)
        return await self.repo.reset_for_rerun(execution)

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

            state: dict = {
                "execution_id": execution_id,
                "scenario_name": scenario.name,
                "scenario_description": scenario.description,
                "acceptance_criteria": scenario.acceptance_criteria,
                "test_case_content": self._read_file(scenario.test_case_file),
                "regression_content": self._read_file(scenario.regression_file),
                "template_key": scenario.template_key,
                "inputs": scenario.inputs or {},
                "business_actions": scenario.business_actions or [],
                "expected_results": scenario.expected_results or [],
                "org_credentials": credentials,
                "login_url": org.login_url,
                "auth_method": org.auth_method,
                "instance_url": org.instance_url,
                "artifacts_dir": str(artifacts_dir),
            }

            try:
                execution_registry.check_cancelled(execution_id)
                parse_result = await scenario_parser_node(state)
                state.update(parse_result)
                await event_manager.emit(
                    execution_id, "phase_completed", step_name="Parse Scenario", status="passed"
                )

                execution_registry.check_cancelled(execution_id)
                plan_result = await planner_node(state)
                state.update(plan_result)
                planned_steps = state["planned_steps"]

                for step in planned_steps:
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
                await db.commit()

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

                logger.info("Launching Playwright browser for execution %s", execution_id)
                await browser_manager.start()
                async with browser_manager.new_context(execution_id) as (context, page):
                    state["current_step_index"] = 0
                    state["retry_count"] = 0
                    state["step_results"] = []

                    while state["current_step_index"] < len(planned_steps):
                        execution_registry.check_cancelled(execution_id)
                        current_step = planned_steps[state["current_step_index"]]
                        db_steps = execution.steps
                        db_step = next((s for s in db_steps if s.seq == current_step.seq), None)
                        if db_step:
                            await repo.update_step(
                                db_step, status=StepStatus.RUNNING, started_at=datetime.now(UTC)
                            )
                            await db.commit()

                        exec_result = await executor_node(state, page, on_event)
                        state.update(exec_result)

                        if state["step_results"]:
                            latest = state["step_results"][-1]
                            if db_step:
                                await repo.update_step(
                                    db_step,
                                    status=latest.status,
                                    screenshot_path=latest.screenshot_path,
                                    error=latest.error,
                                    finished_at=datetime.now(UTC),
                                )
                                await db.commit()

                        if state.get("error"):
                            break

                    await event_manager.emit(
                        execution_id, "phase_completed", step_name="Execute Scenario", status="passed"
                    )

                    validation_result = await validation_node(state, page)
                    state.update(validation_result)
                    await event_manager.emit(
                        execution_id,
                        "phase_completed",
                        step_name="Validation",
                        status="passed" if state["validation"].passed else "failed",
                    )

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
                await db.commit()

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

                await event_manager.emit(
                    execution_id,
                    "execution_completed",
                    status=final_status,
                    message=report_data.summary[:500],
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
            finally:
                execution_registry.clear_cancel(execution_id)

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

    def _read_file(self, path: str | None) -> str:
        if not path:
            return "N/A"
        try:
            return Path(path).read_text(encoding="utf-8", errors="ignore")[:5000]
        except Exception:
            return "N/A"


async def run_execution_background(execution_id: UUID) -> None:
    """Standalone entry point for background tasks (uses its own DB session)."""
    try:
        service = ExecutionService.__new__(ExecutionService)
        service.settings = get_settings()
        await ExecutionService.run_execution(service, execution_id)
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
    finally:
        execution_registry.unregister_task(execution_id)


def schedule_execution_run(execution_id: UUID) -> None:
    """Schedule execution on the running event loop (more reliable than BackgroundTasks)."""
    task = asyncio.create_task(run_execution_background(execution_id))
    execution_registry.register_task(execution_id, task)
