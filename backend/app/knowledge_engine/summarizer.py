"""LLM summarization for extracted knowledge entities."""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.brain_llm_router import _redact_secrets, get_brain_llm
from app.knowledge_engine.types import ExtractionResult

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = """You are a Salesforce architect. Given structured metadata about a Salesforce component,
write a concise 2-3 sentence summary explaining what it does and any business rules.
Return JSON: {"summary": "...", "business_rules": ["rule1", "rule2"]}"""


async def summarize_extraction(
    extraction: ExtractionResult,
    *,
    use_llm: bool = True,
) -> tuple[str | None, list[str]]:
    if not use_llm:
        return _fallback_summary(extraction)

    llm = get_brain_llm(temperature=0.2)
    if llm is None:
        return _fallback_summary(extraction)

    payload = {
        "entity_type": extraction.entity_type,
        "name": extraction.name,
        "file_path": extraction.file_path,
        "data": extraction.data,
    }
    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=SUMMARY_PROMPT),
                HumanMessage(content=json.dumps(payload, default=str)[:6000]),
            ]
        )
        text = response.content if isinstance(response.content, str) else str(response.content)
        return _parse_summary_response(text, extraction)
    except Exception as exc:
        logger.warning(
            "Summarization failed for %s: %s",
            extraction.name,
            _redact_secrets(str(exc)),
        )
        return _fallback_summary(extraction)


def _parse_summary_response(
    text: str, extraction: ExtractionResult
) -> tuple[str | None, list[str]]:
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
            summary = data.get("summary")
            rules = data.get("business_rules") or []
            return summary, [str(r) for r in rules]
    except json.JSONDecodeError:
        pass
    return text[:500], _extract_rules_from_data(extraction)


def _fallback_summary(extraction: ExtractionResult) -> tuple[str | None, list[str]]:
    data = extraction.data
    parts = [f"{extraction.entity_type} {extraction.name}"]
    if extraction.entity_type == "ApexClass":
        methods = data.get("methods", [])
        if methods:
            parts.append(f"Methods: {', '.join(m['name'] for m in methods[:5])}")
        if data.get("soql_objects"):
            parts.append(f"Reads: {', '.join(data['soql_objects'][:5])}")
        if data.get("objects_written"):
            parts.append(f"Writes: {', '.join(data['objects_written'][:5])}")
    elif extraction.entity_type == "LwcComponent":
        if data.get("apex_calls"):
            parts.append(f"Calls Apex: {', '.join(a['method'] for a in data['apex_calls'][:3])}")
        if data.get("fields"):
            parts.append(f"Fields: {', '.join(data['fields'][:5])}")
    elif extraction.entity_type == "ValidationRule":
        if data.get("error_message"):
            parts.append(f"Rule: {data['error_message']}")
    return ". ".join(parts), _extract_rules_from_data(extraction)


def _extract_rules_from_data(extraction: ExtractionResult) -> list[str]:
    rules: list[str] = []
    data = extraction.data
    if extraction.entity_type == "ValidationRule" and data.get("error_message"):
        rules.append(data["error_message"])
    if data.get("formula"):
        rules.append(f"Formula: {data['formula'][:200]}")
    return rules
