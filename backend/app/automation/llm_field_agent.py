"""LLM-assisted UI interaction fallback (NVIDIA Nemotron / OpenAI-compatible)."""

import base64
import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.automation.scope import PageOrFrame, all_scopes
from app.core.llm import get_automation_llm, is_llm_configured

logger = logging.getLogger(__name__)

DUMP_UI_JS = """
() => {
  const items = [];
  const walk = (node) => {
    if (!node) return;
    const els = node.querySelectorAll
      ? node.querySelectorAll('input, button, [role="combobox"], [role="option"], label, span, div')
      : [];
    for (const el of els) {
      const text = (el.textContent || '').trim().replace(/\\s+/g, ' ');
      const ph = (el.placeholder || '').trim();
      const aria = (el.getAttribute('aria-label') || '').trim();
      const role = el.getAttribute('role') || el.tagName.toLowerCase();
      const r = el.getBoundingClientRect();
      if (r.width < 8 || r.height < 6) continue;
      const st = window.getComputedStyle(el);
      if (st.display === 'none' || st.visibility === 'hidden') continue;
      const label = [text, ph, aria].filter(Boolean).join(' | ').slice(0, 100);
      if (!label) continue;
      items.push({
        index: items.length,
        role,
        label,
        x: Math.round(r.x + r.width / 2),
        y: Math.round(r.y + r.height / 2),
      });
      if (items.length >= 40) return;
    }
    const kids = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (const el of kids) {
      if (el.shadowRoot) walk(el.shadowRoot);
      if (items.length >= 40) return;
    }
  };
  walk(document);
  return items;
}
"""


async def _dump_ui(scope: PageOrFrame) -> list[dict]:
    try:
        raw = await scope.evaluate(DUMP_UI_JS)
        return list(raw or [])
    except Exception:
        return []


def _parse_llm_json(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
    return None


async def llm_click_target(
    scope: PageOrFrame,
    *,
    field_label: str,
    task: str,
) -> tuple[int, int] | None:
    if not is_llm_configured():
        return None

    llm = get_automation_llm(temperature=0.1)
    if not llm:
        return None

    elements = await _dump_ui(scope)
    if not elements:
        return None

    # Text-only prompt (faster than vision for Nemotron)
    system = (
        "Reply with ONLY JSON: {\"index\": <number>} for the element to click."
    )
    user_text = (
        f"Task: {task}\nField: {field_label}\n"
        f"Elements:\n{json.dumps(elements[:25], indent=2)}"
    )

    try:
        response = await llm.ainvoke(
            [SystemMessage(content=system), HumanMessage(content=user_text)],
        )
        parsed = _parse_llm_json(str(response.content))
        if parsed and "index" in parsed:
            idx = int(parsed["index"])
            for el in elements:
                if el.get("index") == idx:
                    return int(el["x"]), int(el["y"])
    except Exception as exc:
        logger.warning("LLM click target failed: %s", exc)
    return None


async def llm_assisted_picklist(
    page,
    field_label: str,
    value: str | None,
    *,
    pick_any: bool,
) -> str | None:
    """Single LLM click to open, then deterministic option pick from UI dump."""
    for scope in all_scopes(page):
        coords = await llm_click_target(
            scope,
            field_label=field_label,
            task=f"Click '{field_label}' combobox (placeholder 'Select Sales Office')",
        )
        if not coords:
            continue
        await scope.mouse.click(coords[0], coords[1])
        await scope.wait_for_timeout(600)

        elements = await _dump_ui(scope)
        options = [
            e for e in elements
            if re.search(r"K\d{3}|FSV Recipient", e.get("label", ""), re.I)
        ]
        if not options:
            continue

        choice = options[0]
        if not pick_any and value:
            code = value.strip().upper()
            match = next((o for o in options if code in o.get("label", "").upper()), None)
            if not match:
                return None
            choice = match

        await scope.mouse.click(int(choice["x"]), int(choice["y"]))
        label = choice.get("label", "").split("|")[0].strip()
        logger.info("LLM assisted pick %s: %s", field_label, label)
        return label or None
    return None
