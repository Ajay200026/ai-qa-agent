"""Deterministic checks for expected results — delegates to assertion engine when possible."""

from playwright.async_api import Page

from app.automation.assertions import run_assertion
from app.automation.form_field import field_present, find_input, resolve_form_scope
from app.automation.scope import all_scopes
from app.workflows.action_mapping import infer_assertions_from_expected


async def check_expected(page: Page, expected: str, db=None) -> tuple[bool, str]:
    assertions = infer_assertions_from_expected(expected)
    if assertions:
        for assertion in assertions:
            passed, detail, _ = await run_assertion(page, assertion, db=db)
            if not passed:
                return False, detail
        return True, f"All assertions passed for: {expected}"

    lower = expected.lower()

    if "primary group" in lower and ("editable" in lower or "read-only" in lower or "greyed" in lower):
        from app.schemas.test_case import Assertion, AssertionKind

        kind = (
            AssertionKind.FIELD_READONLY
            if "read-only" in lower or "not editable" in lower or "greyed" in lower
            else AssertionKind.FIELD_EDITABLE
        )
        passed, detail, _ = await run_assertion(
            page, Assertion(kind=kind, target="Primary Group"), db=db,
        )
        return passed, detail

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

        return False, "Primary Group present but assertion too vague — specify editable/value check"

    from app.schemas.test_case import Assertion, AssertionKind

    passed, detail, _ = await run_assertion(
        page, Assertion(kind=AssertionKind.TEXT_VISIBLE, expected=expected), db=db,
    )
    if passed:
        return True, detail

    for candidate in all_scopes(page):
        try:
            loc = candidate.get_by_text(expected, exact=False).first
            if await loc.is_visible(timeout=3000):
                return True, f"Found text: {expected}"
        except Exception:
            continue
    return False, f"Could not verify: {expected}"
