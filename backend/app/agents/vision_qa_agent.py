"""Vision QA agent — Gemma (multi) or Devstral text fallback (single)."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.brain_llm_router import get_vision_llm, is_multi_agent_mode
from app.knowledge.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)

VISION_SYSTEM = """You are a Salesforce UI validation assistant.
Analyze the test step context and report JSON:
{"component":"","validation_passed":true,"anomalies":[],"summary":""}"""


async def run_vision_qa(
    execution_id: str,
    scenario_name: str,
    step_action: str,
    expected: str,
    screenshot_path: str | None,
    dom_summary: str = "",
) -> dict:
    llm = get_vision_llm(temperature=0.1)
    if llm is None:
        return {"validation_passed": True, "summary": "Vision LLM not configured"}

    use_image = is_multi_agent_mode() and screenshot_path and Path(screenshot_path).exists()
    if use_image:
        image_data = Path(screenshot_path).read_bytes()
        b64 = base64.standard_b64encode(image_data).decode()
        content: list = [
            {"type": "text", "text": f"Scenario: {scenario_name}\nStep: {step_action}\nExpected: {expected}"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]
        messages = [SystemMessage(content=VISION_SYSTEM), HumanMessage(content=content)]
    else:
        text = (
            f"Scenario: {scenario_name}\nStep: {step_action}\nExpected: {expected}\n"
            f"Screenshot file: {screenshot_path or 'none'}\nDOM: {dom_summary[:1500]}"
        )
        messages = [SystemMessage(content=VISION_SYSTEM), HumanMessage(content=text)]

    try:
        response = await llm.ainvoke(messages)
        raw = response.content if isinstance(response.content, str) else str(response.content)
        result = json.loads(raw) if raw.strip().startswith("{") else {"summary": raw, "validation_passed": True}
    except Exception:
        logger.exception("Vision QA failed")
        result = {"validation_passed": False, "summary": "Vision analysis error"}

    await _store_vision_memory(execution_id, scenario_name, step_action, result)
    return result


async def _store_vision_memory(
    execution_id: str, scenario_name: str, step_action: str, result: dict
) -> None:
    try:
        await neo4j_client.run_query(
            """
            MERGE (v:KeNode:VisionMemory {id: $id})
            SET v.type = 'VisionMemory', v.name = $screen, v.label = $screen,
                v.summary = $summary, v.validation_passed = $passed, v.orbit_level = 5
            """,
            {
                "id": f"vision:{execution_id}:{step_action}",
                "screen": f"{scenario_name}/{step_action}",
                "summary": result.get("summary", ""),
                "passed": result.get("validation_passed", False),
            },
        )
    except Exception:
        logger.debug("Vision memory store skipped")
