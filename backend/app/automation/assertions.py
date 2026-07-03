"""Typed assertion engine (deterministic-first, LLM fallback)."""

from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from playwright.async_api import Page

from app.automation.field_state import get_field_value, is_field_editable, is_field_readonly, value_matches
from app.automation.pages.base_page import BasePage
from app.automation.scope import all_scopes
from app.core.llm import get_automation_llm, is_llm_configured
from app.schemas.test_case import Assertion, AssertionKind

logger = logging.getLogger(__name__)


async def wait_for_toast(page: Page, timeout_ms: int = 8000) -> str | None:
    base = BasePage(page)
    elapsed = 0
    while elapsed < timeout_ms:
        text = await base.get_all_toast_texts()
        if text:
            return text
        await page.wait_for_timeout(250)
        elapsed += 250
    return None


async def assert_no_toast(page: Page, window_ms: int = 3000) -> tuple[bool, str]:
    base = BasePage(page)
    elapsed = 0
    while elapsed < window_ms:
        text = await base.get_all_toast_texts()
        if text:
            return False, f"Unexpected toast: {text}"
        await page.wait_for_timeout(300)
        elapsed += 300
    return True, "No toast appeared within window"


async def run_assertion(page: Page, assertion: Assertion, *, db=None) -> tuple[bool, str, str | None]:
    """Return (passed, detail, actual_value)."""
    kind = assertion.kind
    target = assertion.target
    expected = assertion.expected or ""

    try:
        if kind == AssertionKind.TOAST_CONTAINS:
            toast = await wait_for_toast(page)
            if not toast:
                return False, "No toast appeared", None
            passed = expected.lower() in toast.lower()
            return passed, f"Toast: {toast[:200]}", toast

        if kind == AssertionKind.TOAST_EQUALS:
            toast = await wait_for_toast(page)
            if not toast:
                return False, "No toast appeared", None
            passed = toast.strip() == expected.strip()
            return passed, f"Toast: {toast}", toast

        if kind == AssertionKind.NO_TOAST:
            return await assert_no_toast(page)

        if kind == AssertionKind.FIELD_EDITABLE:
            field = target or "Primary Group"
            passed, detail = await is_field_editable(page, field, db)
            if not passed and is_llm_configured():
                llm_ok, llm_detail = await _llm_yes_no(page, f"Is the field '{field}' editable (not greyed out)?")
                if llm_ok is not None:
                    return llm_ok, llm_detail, None
            return passed, detail, None

        if kind == AssertionKind.FIELD_READONLY:
            field = target or "Business Type Extension"
            passed, detail = await is_field_readonly(page, field, db)
            if not passed and is_llm_configured():
                llm_ok, llm_detail = await _llm_yes_no(page, f"Is the field '{field}' read-only or not editable?")
                if llm_ok is not None:
                    return llm_ok, llm_detail, None
            return passed, detail, None

        if kind == AssertionKind.FIELD_VALUE_EQUALS:
            field = target or ""
            actual = await get_field_value(page, field, db)
            passed = value_matches(actual, expected)
            return passed, f"{field}={actual!r} (expected {expected!r})", actual

        if kind == AssertionKind.FIELD_PRESENT:
            field = target or "Primary Group"
            actual = await get_field_value(page, field, db)
            passed = actual != "" or await _field_visible(page, field)
            return passed, f"Field present: {field}", actual

        if kind == AssertionKind.TEXT_VISIBLE:
            for scope in all_scopes(page):
                try:
                    loc = scope.get_by_text(expected, exact=False).first
                    if await loc.is_visible(timeout=5000):
                        return True, f"Found text: {expected}", expected
                except Exception:
                    continue
            return False, f"Text not visible: {expected}", None

        if kind == AssertionKind.TEXT_NOT_VISIBLE:
            for scope in all_scopes(page):
                try:
                    loc = scope.get_by_text(expected, exact=False).first
                    if await loc.is_visible(timeout=2000):
                        return False, f"Text unexpectedly visible: {expected}", expected
                except Exception:
                    continue
            return True, f"Text not visible: {expected}", None

        if kind == AssertionKind.REQUEST_CREATED:
            toast = await wait_for_toast(page, timeout_ms=10_000)
            if toast:
                lower = toast.lower()
                if any(
                    hint in lower
                    for hint in ("created", "success", "submitted", "request id", "saved")
                ):
                    return True, f"Success toast: {toast[:200]}", toast

            patterns = (
                re.compile(r"request\s+(is\s+)?created", re.I),
                re.compile(r"created\s+successfully", re.I),
                re.compile(r"request\s*(id|#)?\s*\d+", re.I),
            )
            for scope in all_scopes(page):
                for pattern in patterns:
                    try:
                        loc = scope.get_by_text(pattern).first
                        if await loc.is_visible(timeout=3000):
                            return True, "Request created indicator visible", None
                    except Exception:
                        continue
            return False, "Request not submitted — no success message or request ID visible", None

        if kind == AssertionKind.STATUS_SUBMITTED:
            toast = await wait_for_toast(page, timeout_ms=5000)
            if toast and "submit" in toast.lower():
                return True, f"Submitted: {toast}", toast
            for scope in all_scopes(page):
                try:
                    loc = scope.get_by_text(re.compile(r"submitted", re.I)).first
                    if await loc.is_visible(timeout=3000):
                        return True, "Submitted status visible", None
                except Exception:
                    continue
            return False, "Submitted status not found", None

        return False, f"Unknown assertion kind: {kind}", None
    except Exception as exc:
        logger.warning("Assertion failed: %s", exc)
        return False, str(exc), None


async def _field_visible(page: Page, label: str) -> bool:
    from app.automation.form_field import field_present, resolve_form_scope

    scope = await resolve_form_scope(page, label)
    return await field_present(scope, label)


async def _llm_yes_no(page: Page, question: str) -> tuple[bool | None, str]:
    llm = get_automation_llm(temperature=0)
    if not llm:
        return None, "LLM unavailable"

    dump = await _dump_ui(page)
    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content='Reply ONLY JSON: {"answer": true|false, "reason": "..."}'),
                HumanMessage(content=f"{question}\n\nUI elements:\n{json.dumps(dump[:20], indent=2)}"),
            ]
        )
        parsed = json.loads(str(response.content).strip())
        return bool(parsed.get("answer")), parsed.get("reason", "")
    except Exception as exc:
        return None, str(exc)


DUMP_UI_JS = """
() => {
  const items = [];
  const walk = (node) => {
    if (!node || items.length >= 30) return;
    const els = node.querySelectorAll
      ? node.querySelectorAll('input, button, [role="combobox"], label, span')
      : [];
    for (const el of els) {
      const text = (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 80);
      const aria = (el.getAttribute('aria-label') || '').trim();
      const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true';
      const readonly = el.readOnly || el.getAttribute('aria-readonly') === 'true';
      if (!text && !aria) continue;
      items.push({ label: [text, aria].filter(Boolean).join(' | '), disabled, readonly });
      if (items.length >= 30) return;
    }
    const kids = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (const el of kids) {
      if (el.shadowRoot) walk(el.shadowRoot);
      if (items.length >= 30) return;
    }
  };
  walk(document);
  return items;
}
"""


async def _dump_ui(page: Page) -> list[dict]:
    for scope in all_scopes(page):
        try:
            raw = await scope.evaluate(DUMP_UI_JS)
            if raw:
                return list(raw)
        except Exception:
            continue
    return []
