import logging

from app.agents.state import ExecutionState
from app.schemas.agent import ExecutionReport, StepResult

logger = logging.getLogger(__name__)


async def report_node(state: ExecutionState) -> dict:
    test_pack_result = state.get("test_pack_result")
    trace_events = state.get("trace_events", [])

    if test_pack_result:
        return _report_test_pack(state, test_pack_result, trace_events)

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
        trace_events=trace_events,
    )

    logger.info("Report generated: %s", "PASSED" if overall_passed else "FAILED")
    return {"report": report}


def _report_test_pack(state: ExecutionState, pack_result, trace_events: list) -> dict:
    overall_passed = pack_result.failed_count == 0 and pack_result.blocked_count == 0

    summary_lines = [
        f"Test Pack Report - {pack_result.title or state.get('scenario_name', 'Unknown')}",
        f"Status: {'PASSED' if overall_passed else 'FAILED'}",
        (
            f"Test Cases: {pack_result.passed_count} passed, "
            f"{pack_result.failed_count} failed, "
            f"{pack_result.blocked_count} blocked, "
            f"{pack_result.skipped_count} skipped"
        ),
    ]

    if pack_result.smoke_subset:
        summary_lines.append(f"Smoke subset: {', '.join(pack_result.smoke_subset)}")

    summary_lines.append("")
    for tc in pack_result.test_case_results:
        smoke_tag = " [SMOKE]" if tc.is_smoke else ""
        summary_lines.append(f"  {tc.tc_id}{smoke_tag}: {tc.title} [{tc.status.upper()}]")
        if tc.error:
            summary_lines.append(f"    Error: {tc.error}")
        for step in tc.step_results:
            line = f"    Step {step.seq}. {step.description or step.action} [{step.status}]"
            if step.error:
                line += f" - {step.error}"
            summary_lines.append(line)
            for ar in step.assertion_results:
                summary_lines.append(
                    f"      Assert {ar.kind}: {'PASS' if ar.passed else 'FAIL'} - {ar.detail}"
                )

    flat_steps: list[StepResult] = []
    seq = 1
    for tc in pack_result.test_case_results:
        for step in tc.step_results:
            flat_steps.append(
                StepResult(
                    seq=seq,
                    name=f"{tc.tc_id}: {step.description or step.action}",
                    action=step.action,
                    status=step.status,
                    screenshot_path=step.screenshot_path,
                    error=step.error,
                    logs=step.logs,
                )
            )
            seq += 1

    report = ExecutionReport(
        passed=overall_passed,
        summary="\n".join(summary_lines),
        passed_count=pack_result.passed_count,
        failed_count=pack_result.failed_count + pack_result.blocked_count,
        step_results=flat_steps,
        test_pack_result=pack_result,
        trace_events=trace_events,
    )
    logger.info(
        "Test pack report: %d/%d passed",
        pack_result.passed_count,
        len(pack_result.test_case_results),
    )
    return {"report": report}
