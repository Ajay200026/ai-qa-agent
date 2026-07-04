"""LLM-powered test pack understanding."""

from __future__ import annotations

import logging

from langchain_core.prompts import ChatPromptTemplate

from app.agents.state import ExecutionState
from app.core.brain_llm_router import get_analysis_llm
from app.core.llm import is_llm_configured
from app.core.privacy import is_sensitive_scenario
from app.schemas.test_case import TestPack
from app.services.test_pack_ingestor import ingest_text
from app.workflows.test_table_parser import is_test_pack, parse_test_pack

logger = logging.getLogger(__name__)

UNDERSTANDING_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a Salesforce QA test analyst. Parse a test case pack into structured TestPack JSON.

Rules:
- Split into individual test cases (TC-01, TC_4900_001, etc.)
- For each step, set action from: login, load_customer, open_customer_details, modify_primary_group,
  change_business_type, set_field, select_sales_office, save_draft, submit, check_field_editable,
  check_field_readonly, read_toast, assert_no_toast, validate_expected
- Infer assertions from Expected Result text:
  - toast/guidance -> toast_contains with exact quoted text when present
  - editable -> field_editable
  - read-only/greyed -> field_readonly
  - field value checks -> field_value_equals
  - no toast -> no_toast
- Extract role and bottler from preconditions (e.g. Northeast (5000), Abarta (4900), Finance)
- smoke_subset: list TC ids in minimum/smoke pack if mentioned""",
    ),
    ("human", "Test pack content:\n\n{content}"),
])


async def understand_test_pack(content: str) -> TestPack:
    text = ingest_text(content)
    if not is_test_pack(text):
        return TestPack()

    base = parse_test_pack(text)

    if not is_llm_configured():
        logger.info("Using rule-based test pack parser (no LLM)")
        return base

    llm = get_analysis_llm(temperature=0)
    if not llm:
        return base

    try:
        structured = llm.with_structured_output(TestPack)
        parsed: TestPack = await structured.ainvoke(
            UNDERSTANDING_PROMPT.format_messages(content=text[:12000])
        )
        if not parsed.test_cases:
            return base
        if not parsed.smoke_subset and base.smoke_subset:
            parsed.smoke_subset = base.smoke_subset
        logger.info("LLM parsed test pack: %d test cases", len(parsed.test_cases))
        return parsed
    except Exception as exc:
        logger.warning("LLM test pack parse failed, using rule-based: %s", exc)
        return base


async def test_understanding_node(state: ExecutionState) -> dict:
    content = state.get("test_pack_content") or state.get("test_case_content", "")
    if not content or content == "N/A":
        return {}

    if is_sensitive_scenario(state):
        logger.info(
            "Skipping LLM test pack parser — sensitive customer_target present"
        )
        pack = parse_test_pack(ingest_text(content)) if is_test_pack(content) else TestPack()
        return {"test_pack": pack, "is_test_pack_run": bool(pack.test_cases)}

    pack = await understand_test_pack(content)
    return {"test_pack": pack, "is_test_pack_run": bool(pack.test_cases)}
