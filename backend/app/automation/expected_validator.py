"""Deterministic checks for expected results from scenarios."""

import re

from playwright.async_api import Page

from app.automation.form_field import field_present, find_input, resolve_form_scope
from app.automation.scope import all_scopes


async def check_expected(page: Page, expected: str) -> tuple[bool, str]:
    lower = expected.lower()

    if "request created" in lower:
        found = await _any_visible(
            page,
            [
                page.get_by_text(re.compile(r"request\s*(id|#)?\s*\d+", re.I)),
                page.locator("table tbody tr").first,
                page.get_by_text(re.compile(r"success", re.I)),
            ],
        )
        return found, "Request row or success indicator visible" if found else "No request created indicator"

    if "status submitted" in lower or ("submitted" in lower and "primary" not in lower):
        found = await _any_visible(
            page,
            [
                page.get_by_text(re.compile(r"submitted", re.I)),
                page.get_by_text(re.compile(r"status.*submitted", re.I)),
                page.locator('[role="status"]'),
            ],
        )
        toast = await page.locator(".slds-notify, [role='status']").first.text_content() if found else None
        return found, f"Submitted status found: {toast or 'visible'}" if found else "Submitted status not found"

    if "primary group" in lower:
        scope = await resolve_form_scope(page, "Primary Group")
        if not await field_present(scope, "Primary Group"):
            return False, "Primary Group field not found on page"

        if "updated" in lower or "saved" in lower or "populated" in lower:
            try:
                inp = await find_input(scope, "Primary Group")
                value = (await inp.input_value() or await inp.text_content() or "").strip()
                empty_values = {"", "select", "select primary group", "select..."}
                if not value or value.lower() in empty_values:
                    return False, f"Primary Group empty or not set (value={value!r})"
                return True, f"Primary Group value set: {value}"
            except Exception as exc:
                return False, f"Primary Group value not readable: {exc}"

        return True, "Primary Group field present"

    if "draft saved" in lower:
        found = await _any_visible(
            page,
            [page.get_by_text(re.compile(r"draft\s+saved", re.I)), page.get_by_text(re.compile(r"saved", re.I))],
        )
        return found, "Draft saved message visible" if found else "Draft saved message not found"

    for candidate in all_scopes(page):
        try:
            loc = candidate.get_by_text(expected, exact=False).first
            if await loc.is_visible(timeout=5000):
                return True, f"Found text: {expected}"
        except Exception:
            continue
    return False, f"Could not verify: {expected}"


async def _any_visible(page: Page, locators: list) -> bool:
    for loc in locators:
        try:
            if await loc.first.is_visible(timeout=3000):
                return True
        except Exception:
            continue
    return False
