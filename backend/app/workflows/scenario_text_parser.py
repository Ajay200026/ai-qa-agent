"""Parse structured scenario text into template_key, inputs, actions, expected."""

import json
import re

from app.schemas.parsed_scenario import BusinessAction, ParsedScenario


def _parse_key_value_block(text: str, section: str) -> dict[str, str]:
    pattern = rf"{section}\s*:?\s*\n(.*?)(?=\n(?:Actions|Expected|Template|Acceptance)\s*:|$)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        return {}
    block = match.group(1)
    result: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        kv = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*[=:]\s*(.+)$", line)
        if kv:
            result[kv.group(1)] = kv.group(2).strip().strip('"').strip("'")
    return result


def _parse_list_section(text: str, section: str) -> list[str]:
    pattern = rf"{section}\s*:?\s*\n(.*?)(?=\n(?:Actions|Expected|Inputs|Template|Acceptance)\s*:|$)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        return []
    items: list[str] = []
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*]\s*", "", line)
        if line:
            items.append(line)
    return items


def _parse_actions(text: str) -> list[BusinessAction]:
    pattern = r"Actions\s*:?\s*\n(.*?)(?=\nExpected\s*:|$)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        return []
    actions: list[BusinessAction] = []
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*]\s*", "", line)
        if "=" in line:
            action_part, value = [p.strip() for p in line.split("=", 1)]
            actions.append(BusinessAction(action=action_part, value=value, description=line))
        else:
            actions.append(BusinessAction(action=line, description=line))
    return actions


def parse_scenario_text(
    text: str,
    *,
    template_key: str | None = None,
    inputs: dict | None = None,
    business_actions: list | None = None,
    expected_results: list | None = None,
) -> ParsedScenario:
    combined = text or ""

    tpl_match = re.search(r"template\s*[=:]\s*([A-Z_]+)", combined, re.IGNORECASE)
    resolved_template = (
        template_key
        or (tpl_match.group(1).upper() if tpl_match else None)
        or "DATA_CHANGE_REQUEST"
    )

    parsed_inputs = _parse_key_value_block(combined, "Inputs")
    if inputs:
        parsed_inputs.update(inputs)

    request_module = re.search(
        r"request\s+module\s*[=:]\s*['\"]?([^'\".\n]+)['\"]?",
        combined,
        re.IGNORECASE,
    )
    if request_module and "RequestModule" not in parsed_inputs:
        parsed_inputs["RequestModule"] = request_module.group(1).strip()

    actions = _parse_actions(combined)
    if business_actions:
        for raw in business_actions:
            if isinstance(raw, dict):
                actions.append(BusinessAction(**raw))
            elif isinstance(raw, str):
                actions.append(BusinessAction(action=raw, description=raw))

    expected = _parse_list_section(combined, "Expected")
    if expected_results:
        expected.extend(expected_results)

    if not actions and "primary group" in combined.lower():
        pg = re.search(
            r"primary\s+group\s*[=:]\s*['\"]?([^'\".\n]+)['\"]?",
            combined,
            re.IGNORECASE,
        )
        actions = [
            BusinessAction(action="Open Customer Details", description="Open Customer Details"),
            BusinessAction(
                action="Update Primary Group",
                value=pg.group(1).strip() if pg else "Default",
                description="Update Primary Group",
            ),
            BusinessAction(action="Submit", description="Submit"),
        ]

    if not expected and "submitted" in combined.lower():
        expected = ["Request Created", "Status Submitted"]

    return ParsedScenario(
        template_key=resolved_template,
        inputs=parsed_inputs,
        business_actions=actions,
        expected_results=expected,
        objective=combined[:200],
    )
