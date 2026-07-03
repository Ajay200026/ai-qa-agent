"""Natural-language -> executor action and assertion inference."""

from __future__ import annotations

import re

from app.schemas.test_case import Assertion, AssertionKind

ACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"log\s*in", re.I), "login"),
    (re.compile(r"open\s+data\s+change", re.I), "create_data_change_request"),
    (re.compile(r"load\s+(?:an?\s+)?(?:sv|dsd|secondary|active)?\s*customer", re.I), "load_customer"),
    (re.compile(r"search\s+and\s+load", re.I), "load_customer"),
    (re.compile(r"open\s+customer\s+details", re.I), "open_customer_details"),
    (re.compile(r"primary\s+group", re.I), "modify_primary_group"),
    (re.compile(r"business\s+type\s+extension", re.I), "set_field"),
    (re.compile(r"change\s+business\s+type|business\s+type\s+(?:from|to)", re.I), "change_business_type"),
    (re.compile(r"select\s+sales\s+office", re.I), "select_sales_office"),
    (re.compile(r"customer\s+search|search\s+customer", re.I), "open_customer_search"),
    (re.compile(r"save\s+(?:the\s+)?(?:request|draft)", re.I), "save_draft"),
    (re.compile(r"submit", re.I), "submit"),
    (re.compile(r"check\s+.*editable|field\s+is\s+editable", re.I), "check_field_editable"),
    (re.compile(r"check\s+.*read[- ]?only|field\s+is\s+not\s+editable|greyed\s+out", re.I), "check_field_readonly"),
    (re.compile(r"read\s+toast|toast\s+message", re.I), "read_toast"),
    (re.compile(r"no\s+toast|toast.*not\s+appear", re.I), "assert_no_toast"),
    (re.compile(r"verify\s+fields?", re.I), "validate_expected"),
    (re.compile(r"observe\s+guidance", re.I), "assert_no_toast"),
]


def infer_action_from_text(text: str) -> str | None:
    for pattern, action in ACTION_PATTERNS:
        if pattern.search(text):
            return action
    if "change" in text.lower() and "field" in text.lower():
        return "set_field"
    return None


def infer_assertions_from_expected(expected: str) -> list[Assertion]:
    if not expected or not expected.strip():
        return []

    lower = expected.lower()
    assertions: list[Assertion] = []

    if "toast" in lower and ("not" in lower or "no " in lower):
        assertions.append(Assertion(kind=AssertionKind.NO_TOAST))
    elif "toast" in lower or "guidance" in lower:
        quoted = re.findall(r'"([^"]+)"', expected)
        if quoted:
            assertions.append(
                Assertion(kind=AssertionKind.TOAST_CONTAINS, expected=quoted[0])
            )
        else:
            assertions.append(Assertion(kind=AssertionKind.TOAST_CONTAINS, expected=expected.strip()))

    if "editable" in lower and "not" not in lower and "read-only" not in lower:
        field = _field_from_text(expected) or "Primary Group"
        assertions.append(Assertion(kind=AssertionKind.FIELD_EDITABLE, target=field))

    if "read-only" in lower or "not editable" in lower or "greyed" in lower:
        field = _field_from_text(expected) or "Business Type Extension"
        assertions.append(Assertion(kind=AssertionKind.FIELD_READONLY, target=field))

    if "bt =" in lower or "business type" in lower and "=" in lower:
        m = re.search(r"=\s*([A-Za-z0-9\s()]+)", expected)
        if m:
            assertions.append(
                Assertion(
                    kind=AssertionKind.FIELD_VALUE_EQUALS,
                    target="Business Type",
                    expected=m.group(1).strip(),
                )
            )

    if "bte" in lower or "business type extension" in lower:
        m = re.search(r"=\s*([A-Za-z0-9]+)", expected)
        if m:
            assertions.append(
                Assertion(
                    kind=AssertionKind.FIELD_VALUE_EQUALS,
                    target="Business Type Extension",
                    expected=m.group(1).strip(),
                )
            )

    if expects_request_submission(expected):
        assertions.append(Assertion(kind=AssertionKind.REQUEST_CREATED))

    if "submitted" in lower and "not" not in lower:
        assertions.append(Assertion(kind=AssertionKind.STATUS_SUBMITTED))

    if not assertions:
        assertions.append(Assertion(kind=AssertionKind.TEXT_VISIBLE, expected=expected.strip()))

    return assertions


def expects_request_submission(text: str) -> bool:
    """True when expected result implies the Data Change request was submitted."""
    if not text or not text.strip():
        return False
    lower = text.lower()
    if re.search(r"request\s+(is\s+)?created", lower):
        return True
    if re.search(r"created\s+successfully", lower):
        return True
    if re.search(r"submission\s+succeed", lower):
        return True
    if "request created" in lower:
        return True
    return False


def _field_from_text(text: str) -> str | None:
    for field in (
        "Primary Group",
        "Business Type Extension",
        "Business Type",
        "Sales Office",
    ):
        if field.lower() in text.lower():
            return field
    return None
