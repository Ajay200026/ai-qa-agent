"""NVIDIA Gemma enrichment — business logic, scenarios, defects for brain/graph prep."""

from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.brain_llm_router import _redact_secrets, get_brain_llm
from app.knowledge_engine.types import ExtractionResult

logger = logging.getLogger(__name__)

TICKET_RE = re.compile(r"\b(US-\d+|[A-Z]{2,}-\d+)\b")

ENRICH_SYSTEM = """You are a Salesforce repository intelligence analyst.
Given code excerpts, extract structured JSON only (no markdown):
{
  "business_logic": [{"name": "", "description": "", "rules": [], "components": [], "functions": [], "source_files": []}],
  "scenarios": [{"name": "", "steps": [], "expected": "", "business_logic": []}],
  "defects": [{"ticket": "", "name": "", "summary": ""}]
}
Ground everything in the provided code. Do not invent components."""


async def enrich_module_extractions(
    module_name: str,
    extractions: list[ExtractionResult],
    *,
    use_llm: bool = True,
) -> dict:
    llm = get_brain_llm(temperature=0.2) if use_llm else None
    enrichment: dict = {"business_logic": [], "scenarios": [], "defects": []}

    for ext in extractions:
        text_blob = json.dumps(ext.data)
        for ticket in TICKET_RE.findall(text_blob):
            enrichment["defects"].append(
                {"ticket": ticket, "name": ticket, "summary": f"Found in {ext.name}"}
            )

    if llm is None:
        return enrichment

    components = [e for e in extractions if e.entity_type in ("LwcComponent", "ApexClass", "Flow")][:8]
    for comp in components:
        excerpt = _build_excerpt(comp)
        if len(excerpt) < 50:
            continue
        try:
            messages = [
                SystemMessage(content=ENRICH_SYSTEM),
                HumanMessage(
                    content=f"Module: {module_name}\nComponent: {comp.name} ({comp.entity_type})\n\n{excerpt}"
                ),
            ]
            response = await llm.ainvoke(messages)
            content = response.content if isinstance(response.content, str) else str(response.content)
            parsed = _parse_json(content)
            if parsed:
                enrichment["business_logic"].extend(parsed.get("business_logic", []))
                enrichment["scenarios"].extend(parsed.get("scenarios", []))
                enrichment["defects"].extend(parsed.get("defects", []))
        except Exception as exc:
            logger.exception(
                "Brain enrichment failed for %s: %s", comp.name, _redact_secrets(str(exc))
            )

    return _dedupe_enrichment(enrichment)


def _build_excerpt(comp: ExtractionResult) -> str:
    parts = [f"Name: {comp.name}", f"Type: {comp.entity_type}"]
    for key in ("methods", "functions", "apex_calls", "wire_methods", "events_handled"):
        if comp.data.get(key):
            parts.append(f"{key}: {json.dumps(comp.data[key])[:800]}")
    return "\n".join(parts)


def _parse_json(content: str) -> dict | None:
    content = content.strip()
    if "```" in content:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if match:
            content = match.group(1)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def _dedupe_enrichment(data: dict) -> dict:
    seen: set[str] = set()
    result = {"business_logic": [], "scenarios": [], "defects": []}
    for key in result:
        for item in data.get(key, []):
            ident = item.get("ticket") or item.get("name", "")
            if ident and ident in seen:
                continue
            if ident:
                seen.add(ident)
            result[key].append(item)
    return result
