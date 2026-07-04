"""Root Cause Analysis agent — Devstral (single) or Qwen (multi)."""

from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.brain_llm_router import get_rca_llm
from app.knowledge.neo4j_client import neo4j_client
from app.schemas.agent import ExecutionReport, StepResult
from app.schemas.rca import RCAAnalysis

logger = logging.getLogger(__name__)

RCA_SYSTEM = """You are a Salesforce QA root cause analyst.
Analyze the failed test using graph context and step errors.
Return JSON only:
{"what_failed":"","why_failed":"","where_failed":"file:line if known","business_impact":"","suggested_fix":"","graph_path":[]}
Recommend fixes only — never output modified code."""


async def run_rca_analysis(
    scenario_id: str,
    scenario_name: str,
    report: ExecutionReport,
    step_results: list[StepResult],
    execution_id: str,
) -> RCAAnalysis | None:
    llm = get_rca_llm(temperature=0.2)
    if llm is None:
        return None

    failed_steps = [s for s in step_results if s.status != "passed"]
    graph_context = await _fetch_graph_context(scenario_id)
    prompt = (
        f"Scenario: {scenario_name}\n"
        f"Execution: {execution_id}\n"
        f"Summary: {report.summary}\n"
        f"Failed steps: {json.dumps([{'action': s.action, 'error': s.error} for s in failed_steps])}\n"
        f"Graph context: {json.dumps(graph_context)[:3000]}"
    )

    try:
        response = await llm.ainvoke(
            [SystemMessage(content=RCA_SYSTEM), HumanMessage(content=prompt)]
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        parsed = _parse_json(content)
        if parsed:
            return RCAAnalysis(**parsed)
    except Exception:
        logger.exception("RCA analysis failed")
    return RCAAnalysis(
        what_failed=report.summary[:500],
        why_failed=failed_steps[0].error if failed_steps else "Unknown",
        where_failed="",
        business_impact="Test execution failed",
        suggested_fix="Review failed step and related code in Knowledge graph",
        graph_path=[],
    )


async def _fetch_graph_context(scenario_id: str) -> list[dict]:
    try:
        return await neo4j_client.run_query(
            """
            MATCH (s:KeNode)
            WHERE s.scenario_id = $sid OR (s.type = 'Scenario' AND s.name IS NOT NULL)
            OPTIONAL MATCH (s)-[r*1..2]-(n:KeNode)
            RETURN s.name as scenario, collect(DISTINCT n.name) as related
            LIMIT 5
            """,
            {"sid": scenario_id},
        )
    except Exception:
        return []


def _parse_json(content: str) -> dict | None:
    if "```" in content:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if match:
            content = match.group(1)
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        return None
