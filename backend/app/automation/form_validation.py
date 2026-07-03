"""Detect Salesforce Data Change submit outcomes and empty required fields."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from playwright.async_api import Page

from app.automation.assertions import wait_for_toast
from app.automation.field_state import get_field_value
from app.automation.pages.base_page import BasePage
from app.knowledge.data_change_field_registry import get_field_by_label, get_required_fields_for_bottler

SubmitStatus = Literal["success", "validation_error", "unknown"]

SUCCESS_PATTERNS = re.compile(
    r"request\s+(is\s+)?created|created\s+successfully|submitted|request\s*(id|#)?\s*\d+",
    re.I,
)
VALIDATION_ERROR_PATTERNS = re.compile(
    r"required|complete this field|select a value|select an option|missing|invalid|error",
    re.I,
)

EMPTY_VALUE_PATTERNS = re.compile(
    r"^(select|search|enter|\.\.\.).*$",
    re.I,
)


@dataclass
class SubmitOutcome:
    status: SubmitStatus
    message: str = ""
    missing_field_labels: list[str] | None = None


def _extract_field_labels_from_text(text: str) -> list[str]:
    labels: list[str] = []
    if not text:
        return labels
    for pattern in (
        r"field[s]?\s*[:\-]?\s*([A-Za-z][A-Za-z0-9\s/&]+?)(?:\s+is|\s+are|\.|$)",
        r"([A-Za-z][A-Za-z0-9\s/&]{2,40})\s+is required",
        r"complete\s+([A-Za-z][A-Za-z0-9\s/&]+)",
    ):
        for match in re.finditer(pattern, text, re.I):
            label = match.group(1).strip().rstrip(":")
            if label and len(label) > 2:
                labels.append(label)
    return labels


async def _dom_validation_errors(page: Page) -> list[str]:
    labels: list[str] = []
    try:
        raw = await page.evaluate(
            """
() => {
  const out = [];
  const walk = (node) => {
    if (!node) return;
    const els = node.querySelectorAll
      ? node.querySelectorAll('.slds-has-error, [aria-invalid="true"]')
      : [];
    for (const el of els) {
      const root = el.closest('.slds-form-element, tr, fieldset') || el.parentElement;
      if (!root) continue;
      const lbl = root.querySelector('label, .slds-form-element__label, th, abbr');
      const text = (lbl && lbl.textContent || '').replace(/\\s+/g, ' ').trim();
      if (text && text.length > 2 && text.length < 80) out.push(text.replace(/\\*$/, '').trim());
    }
    const kids = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (const el of kids) {
      if (el.shadowRoot) walk(el.shadowRoot);
    }
  };
  walk(document);
  return [...new Set(out)];
}
"""
        )
        labels.extend(str(x).strip() for x in (raw or []) if str(x).strip())
    except Exception:
        pass
    return labels


def is_empty_field_value(value: str, placeholder: str | None = None) -> bool:
    text = (value or "").strip()
    if not text:
        return True
    if EMPTY_VALUE_PATTERNS.match(text):
        return True
    if placeholder and text.lower() == placeholder.lower():
        return True
    return False


async def scan_empty_required_fields(page: Page, bottler_id: str, *, db=None) -> list[str]:
    """Return labels of bottler-required fields that appear empty on the form."""
    empty: list[str] = []
    for field in get_required_fields_for_bottler(bottler_id):
        if field.section == "REQUEST_FORM":
            continue
        try:
            value = await get_field_value(page, field.label, db)
        except Exception:
            value = ""
        if is_empty_field_value(value, field.placeholder):
            empty.append(field.label)
    return empty


async def detect_submit_outcome(page: Page, *, bottler_id: str | None = None, db=None) -> SubmitOutcome:
    """Classify the page state after clicking Submit."""
    base = BasePage(page)
    toast = await wait_for_toast(page, timeout_ms=8_000)
    page_text = ""
    try:
        page_text = await page.evaluate("() => document.body.innerText.slice(0, 4000)")
    except Exception:
        pass

    combined = f"{toast or ''} {page_text}"
    dom_errors = await _dom_validation_errors(page)

    if toast and SUCCESS_PATTERNS.search(toast):
        return SubmitOutcome(status="success", message=toast[:300])

    if SUCCESS_PATTERNS.search(page_text):
        return SubmitOutcome(status="success", message="Request created indicator on page")

    try:
        from app.automation.pages.data_change_page import DataChangePage

        dc = DataChangePage(page, db=db)
        if await dc.has_success_message():
            return SubmitOutcome(status="success", message="Success message visible")
    except Exception:
        pass

    missing: list[str] = []
    if toast:
        missing.extend(_extract_field_labels_from_text(toast))
    missing.extend(dom_errors)

    if bottler_id:
        missing.extend(await scan_empty_required_fields(page, bottler_id, db=db))

    seen: set[str] = set()
    deduped: list[str] = []
    for label in missing:
        norm = label.strip().lower()
        if norm and norm not in seen:
            seen.add(norm)
            matched = get_field_by_label(label)
            deduped.append(matched.label if matched else label.strip())

    is_validation = bool(deduped)
    if toast and VALIDATION_ERROR_PATTERNS.search(toast):
        is_validation = True
    if dom_errors and not SUCCESS_PATTERNS.search(combined):
        is_validation = True

    if is_validation:
        return SubmitOutcome(
            status="validation_error",
            message=(toast or "Required fields missing on form")[:300],
            missing_field_labels=deduped or None,
        )

    if toast:
        return SubmitOutcome(status="unknown", message=toast[:300])

    return SubmitOutcome(status="unknown", message="No submit feedback detected")
