"""Field state probes: editable, readonly, value reading."""

from __future__ import annotations

import re

from playwright.async_api import Locator, Page

from app.automation.field_resolver import SmartFieldResolver
from app.automation.form_field import field_present, find_input, resolve_form_scope


async def get_field_locator(page: Page, label: str, db=None) -> Locator | None:
    scope = await resolve_form_scope(page, label)
    if await field_present(scope, label):
        try:
            return await find_input(scope, label)
        except Exception:
            pass
    resolver = SmartFieldResolver(page, "DATA_CHANGE_REQUEST", db)
    resolved = await resolver.resolve(label)
    if resolved.locator:
        return resolved.locator
    return None


async def get_field_value(page: Page, label: str, db=None) -> str:
    loc = await get_field_locator(page, label, db)
    if not loc:
        return ""
    try:
        val = (await loc.input_value() or "").strip()
        if val:
            return val
    except Exception:
        pass
    try:
        return (await loc.text_content() or "").strip()
    except Exception:
        return ""


async def is_field_editable(page: Page, label: str, db=None) -> tuple[bool, str]:
    loc = await get_field_locator(page, label, db)
    if not loc:
        return False, f"Field '{label}' not found"

    editable, reason = await _probe_editable(loc)
    return editable, reason


async def is_field_readonly(page: Page, label: str, db=None) -> tuple[bool, str]:
    editable, reason = await is_field_editable(page, label, db)
    if "not found" in reason.lower():
        return False, reason
    return not editable, f"Field readonly: {reason}" if not editable else f"Field is editable: {reason}"


async def _probe_editable(loc: Locator) -> tuple[bool, str]:
    try:
        if await loc.is_disabled():
            return False, "disabled attribute"
    except Exception:
        pass

    try:
        readonly = await loc.get_attribute("readonly")
        if readonly is not None:
            return False, "readonly attribute"
    except Exception:
        pass

    try:
        aria_disabled = await loc.get_attribute("aria-disabled")
        if aria_disabled and aria_disabled.lower() == "true":
            return False, "aria-disabled"
        aria_readonly = await loc.get_attribute("aria-readonly")
        if aria_readonly and aria_readonly.lower() == "true":
            return False, "aria-readonly"
    except Exception:
        pass

    try:
        parent = loc.locator("xpath=ancestor::*[contains(@class,'slds-form-element')][1]")
        cls = (await parent.get_attribute("class") or "").lower()
        if "slds-is-disabled" in cls or "disabled" in cls:
            return False, "slds-is-disabled on parent"
    except Exception:
        pass

    try:
        visible = await loc.is_visible()
        if not visible:
            return False, "not visible"
    except Exception:
        return False, "visibility check failed"

    return True, "editable"


def value_matches(actual: str, expected: str) -> bool:
    if not expected:
        return bool(actual)
    a = re.sub(r"\s+", " ", actual.lower()).strip()
    e = re.sub(r"\s+", " ", expected.lower()).strip()
    return e in a or a in e
