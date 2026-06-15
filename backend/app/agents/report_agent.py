import logging
from datetime import UTC, datetime

from app.agents.state import ExecutionState
from app.schemas.agent import ExecutionReport

logger = logging.getLogger(__name__)


async def report_node(state: ExecutionState) -> dict:
    step_results = state.get("step_results", [])
    validation = state.get("validation")
    passed_count = sum(1 for r in step_results if r.status == "passed")
    failed_count = sum(1 for r in step_results if r.status == "failed")
    overall_passed = validation.passed if validation else failed_count == 0

    summary_lines = [
        f"Execution Report - {state.get('scenario_name', 'Unknown')}",
        f"Status: {'PASSED' if overall_passed else 'FAILED'}",
        f"Steps: {passed_count} passed, {failed_count} failed",
        "",
        "Step Details:",
    ]
    for result in step_results:
        line = f"  {result.seq}. {result.name} [{result.status}]"
        if result.error:
            line += f" - Error: {result.error}"
        summary_lines.append(line)

    if validation and validation.llm_verdict:
        summary_lines.extend(["", "LLM Analysis:", validation.llm_verdict])

    report = ExecutionReport(
        passed=overall_passed,
        summary="\n".join(summary_lines),
        passed_count=passed_count,
        failed_count=failed_count,
        llm_analysis=validation.llm_verdict if validation else None,
        step_results=step_results,
    )

    logger.info("Report generated: %s", "PASSED" if overall_passed else "FAILED")
    return {"report": report}
