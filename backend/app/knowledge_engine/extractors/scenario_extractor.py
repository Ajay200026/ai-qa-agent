"""Extract scenario/defect references from repo documentation."""

from __future__ import annotations

import re
from pathlib import Path

from app.knowledge_engine.types import ExtractionResult

TICKET_PATTERN = re.compile(r"\b(US-\d+|JIRA-\d+|[A-Z]{2,}-\d+)\b")
SCENARIO_HEADER = re.compile(r"^#+\s*(Scenario|Test Case|TC)[:\s]+(.+)$", re.MULTILINE | re.IGNORECASE)
STEP_PATTERN = re.compile(r"^\s*\d+[\.\)]\s+(.+)$", re.MULTILINE)


def extract_scenario_docs(file_path: Path, relative: str) -> list[ExtractionResult]:
    if file_path.suffix.lower() not in (".md", ".txt"):
        return []
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    results: list[ExtractionResult] = []
    tickets = list(dict.fromkeys(TICKET_PATTERN.findall(text)))

    for match in SCENARIO_HEADER.finditer(text):
        name = match.group(2).strip()
        start = match.end()
        next_header = SCENARIO_HEADER.search(text, start)
        block = text[start : next_header.start() if next_header else len(text)]
        steps = [m.group(1).strip() for m in STEP_PATTERN.finditer(block)]

        results.append(
            ExtractionResult(
                entity_type="Scenario",
                name=name,
                file_path=relative,
                data={"steps": steps, "source": "doc", "tickets": tickets},
                references=tickets,
                relationships=[],
            )
        )

    for ticket in tickets:
        results.append(
            ExtractionResult(
                entity_type="Defect",
                name=ticket,
                file_path=relative,
                data={"ticket": ticket, "summary": f"Referenced in {relative}"},
                references=[ticket],
                relationships=[{"type": "CAUSED_BY", "source": ticket, "target": ""}],
            )
        )

    return results
