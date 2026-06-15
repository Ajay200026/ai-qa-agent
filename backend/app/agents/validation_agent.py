import logging

from langchain_core.prompts import ChatPromptTemplate
from playwright.async_api import Page

from app.agents.state import ExecutionState
from app.automation.expected_validator import check_expected
from app.automation.pages.data_change_page import DataChangePage
from app.core.llm import get_chat_llm, is_llm_configured
from app.schemas.agent import ValidationResult

logger = logging.getLogger(__name__)

VALIDATION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a Salesforce QA validator. Evaluate whether the test execution met the acceptance criteria. "
        "Respond with a concise verdict: PASSED or FAILED followed by reasoning.",
    ),
    (
        "human",
        "Acceptance Criteria:\n{acceptance_criteria}\n\n"
        "Expected Results:\n{expected_results}\n\n"
        "Step Results:\n{step_results}\n\n"
        "Deterministic Checks:\n{checks}",
    ),
])


async def validation_node(state: ExecutionState, page: Page | None = None) -> dict:
    checks: list[dict] = []
    all_passed = True

    failed_steps = [r for r in state.get("step_results", []) if r.status == "failed"]
    if failed_steps:
        checks.append({"check": "all_steps_passed", "passed": False, "detail": f"{len(failed_steps)} steps failed"})
        all_passed = False
    else:
        checks.append({"check": "all_steps_passed", "passed": True, "detail": "All steps completed"})

    expected_results = state.get("expected_results") or []
    if page and expected_results:
        for expected in expected_results:
            passed, detail = await check_expected(page, expected)
            checks.append({"check": expected, "passed": passed, "detail": detail})
            if not passed:
                all_passed = False

    if page:
        data_change = DataChangePage(page, template_key=state.get("template_key", "DATA_CHANGE_REQUEST"))
        has_success = await data_change.has_success_message()
        if not expected_results:
            checks.append({
                "check": "success_message",
                "passed": has_success,
                "detail": "Success message visible" if has_success else "No success message found",
            })
            if not has_success:
                all_passed = False

        checks.append({
            "check": "url_state",
            "passed": True,
            "detail": f"Current URL: {page.url}",
        })

    llm_verdict = None
    if is_llm_configured():
        try:
            llm = get_chat_llm(temperature=0)
            if not llm:
                raise RuntimeError("LLM not available")
            step_summary = "\n".join(
                f"- {r.name}: {r.status}" + (f" ({r.error})" if r.error else "")
                for r in state.get("step_results", [])
            )
            response = await llm.ainvoke(
                VALIDATION_PROMPT.format_messages(
                    acceptance_criteria=state.get("acceptance_criteria", ""),
                    expected_results="\n".join(f"- {e}" for e in expected_results),
                    step_results=step_summary,
                    checks=str(checks),
                )
            )
            llm_verdict = response.content
            if llm_verdict and "FAILED" in llm_verdict.upper() and all_passed:
                all_passed = False
        except Exception as exc:
            logger.warning("LLM validation failed: %s", exc)
            llm_verdict = f"LLM validation unavailable: {exc}"

    validation = ValidationResult(passed=all_passed, checks=checks, llm_verdict=llm_verdict)
    logger.info("Validation result: %s", "PASSED" if all_passed else "FAILED")
    return {"validation": validation}
