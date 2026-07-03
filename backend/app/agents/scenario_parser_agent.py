import logging
import json

from langchain_core.prompts import ChatPromptTemplate

from app.agents.state import ExecutionState
from app.core.llm import get_chat_llm, is_llm_configured
from app.core.privacy import is_sensitive_scenario
from app.schemas.parsed_scenario import BusinessAction, ParsedScenario
from app.workflows.scenario_text_parser import parse_scenario_text

logger = logging.getLogger(__name__)

PARSER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a Salesforce QA engineer. Parse ONLY the business-specific parts of a test scenario.
Navigation is handled by a workflow template — do NOT include login, app launcher, or queue navigation steps.

Extract:
- template_key: one of DATA_CHANGE_REQUEST, NEW_CUSTOMER_REQUEST, NEW_FSV_CUSTOMER, NEW_DSD_CUSTOMER, ACCOUNT_RECEIVABLE, CONTACT_UPDATE
- inputs: dict e.g. {{"SalesOffice": "K045", "CustomerNumber": "060", "RequestModule": "NEW DATA CHANGE"}}
- business_actions: list of {{action, value?, field?, description?}} e.g. Open Customer Details, Update Primary Group=TEST_GROUP, Submit
- expected_results: list of strings e.g. Request Created, Status Submitted, Primary Group Saved

Use __any__ for SalesOffice and __first__ for CustomerNumber when not specified.""",
    ),
    (
        "human",
        """Scenario Name: {scenario_name}
Description: {scenario_description}
Acceptance Criteria: {acceptance_criteria}
Test Cases: {test_case_content}
Regression: {regression_content}
Template Key (if set): {template_key}
Inputs JSON (if set): {inputs_json}
Business Actions JSON (if set): {business_actions_json}
Expected Results JSON (if set): {expected_results_json}""",
    ),
])


def _scenario_full_text(state: ExecutionState) -> str:
    parts = [
        state.get("scenario_name", ""),
        state.get("scenario_description", ""),
        state.get("acceptance_criteria", ""),
        state.get("test_case_content", ""),
        state.get("regression_content", ""),
    ]
    return "\n".join(p for p in parts if p and p != "N/A")


def _default_parsed(state: ExecutionState) -> ParsedScenario:
    return parse_scenario_text(
        _scenario_full_text(state),
        template_key=state.get("template_key"),
        inputs=state.get("inputs"),
        business_actions=state.get("business_actions"),
        expected_results=state.get("expected_results"),
    )


async def scenario_parser_node(state: ExecutionState) -> dict:
    base = _default_parsed(state)

    if is_sensitive_scenario(state):
        logger.info(
            "Skipping LLM scenario parser — sensitive customer_target present (privacy guard)"
        )
        return {"parsed_scenario": base}

    if state.get("business_actions") and state.get("template_key"):
        logger.info("Skipping LLM scenario parser — structured inputs already provided")
        return {"parsed_scenario": base}

    if not is_llm_configured():
        logger.info("Using rule-based scenario parser (no LLM)")
        return {"parsed_scenario": base}

    llm = get_chat_llm(temperature=0)
    if not llm:
        return {"parsed_scenario": base}

    try:
        structured_llm = llm.with_structured_output(ParsedScenario)
        parsed: ParsedScenario = await structured_llm.ainvoke(
            PARSER_PROMPT.format_messages(
                scenario_name=state.get("scenario_name", ""),
                scenario_description=state.get("scenario_description", ""),
                acceptance_criteria=state.get("acceptance_criteria", ""),
                test_case_content=state.get("test_case_content", "N/A"),
                regression_content=state.get("regression_content", "N/A"),
                template_key=state.get("template_key") or base.template_key,
                inputs_json=json.dumps(state.get("inputs") or base.inputs),
                business_actions_json=json.dumps(
                    [a.model_dump() for a in base.business_actions]
                ),
                expected_results_json=json.dumps(base.expected_results),
            )
        )
        if state.get("template_key"):
            parsed.template_key = state["template_key"]
        if state.get("inputs"):
            parsed.inputs = {**parsed.inputs, **state["inputs"]}
        if state.get("business_actions"):
            parsed.business_actions = [
                BusinessAction(**a) if isinstance(a, dict) else BusinessAction(action=a)
                for a in state["business_actions"]
            ] or parsed.business_actions
        if state.get("expected_results"):
            parsed.expected_results = state["expected_results"] or parsed.expected_results
        logger.info("LLM parsed scenario: template=%s", parsed.template_key)
        return {"parsed_scenario": parsed}
    except Exception as exc:
        logger.warning("LLM parser failed, using rule-based parser: %s", exc)
        return {"parsed_scenario": base}
