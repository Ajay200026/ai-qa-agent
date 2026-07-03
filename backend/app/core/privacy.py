"""LLM privacy guards for customer-target scenarios.

Goal: customer-targeting data (Account Number, Name, SOQL rows, etc.)
must never reach an LLM prompt or response. We use this to:

1. Detect whether a scenario carries sensitive customer data
   (`is_sensitive_scenario`).
2. Produce a redacted copy of execution state for any code path that
   builds an LLM prompt (`redact_state`).
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Iterable, Mapping

SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "customer_target",
        "login_as_target",
        "identity_map",
        "impersonated_username",
        "resolved_user",
        "soql_query",
        "soql_results",
        "soql_rows",
        "account_number",
        "account_name",
        "customer_number",
        "customer_name",
        "account_query",
        "account_query_id",
        "login_as_profile",
        "login_as_profile_id",
        "soql_text",
    }
)

SENSITIVE_INPUT_KEYS: frozenset[str] = frozenset(
    {"CustomerNumber", "CustomerName", "AccountNumber"}
)

REDACTED = "<REDACTED>"

_ACCOUNT_NUMBER_RE = re.compile(r"\b\d{7,12}\b")


def is_sensitive_scenario(state: Mapping[str, Any] | None) -> bool:
    if not state:
        return False
    if state.get("customer_target"):
        return True
    if state.get("login_as_target"):
        return True
    if state.get("account_query") or state.get("account_query_id"):
        return True
    if state.get("login_as_profile") or state.get("login_as_profile_id"):
        return True
    identity_map = state.get("identity_map")
    if isinstance(identity_map, Mapping):
        entries = identity_map.get("entries")
        if entries:
            return True
    inputs = state.get("inputs") or {}
    if isinstance(inputs, Mapping):
        for key in SENSITIVE_INPUT_KEYS:
            if inputs.get(key):
                return True
    return False


def _collect_account_numbers(state: Mapping[str, Any]) -> set[str]:
    numbers: set[str] = set()

    def _walk(obj: Any) -> None:
        if isinstance(obj, Mapping):
            for k, v in obj.items():
                if k in {"account_number", "AccountNumber", "customer_number", "CustomerNumber"} and v:
                    numbers.add(str(v).strip())
                _walk(v)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _walk(item)

    _walk(state)
    return {n for n in numbers if n}


def _scrub_string(value: str, account_numbers: Iterable[str]) -> str:
    redacted = value
    for number in account_numbers:
        if not number:
            continue
        redacted = redacted.replace(number, REDACTED)
    # Also collapse any obvious 7-12 digit Salesforce-style numbers that look
    # like account numbers anywhere in user-supplied text.
    redacted = _ACCOUNT_NUMBER_RE.sub(REDACTED, redacted)
    return redacted


def redact_state(state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a deep-copied state safe to send to an LLM."""
    if not state:
        return {}
    safe = deepcopy(dict(state))
    numbers = _collect_account_numbers(safe)

    for key in list(safe.keys()):
        if key in SENSITIVE_KEYS:
            safe[key] = REDACTED

    inputs = safe.get("inputs")
    if isinstance(inputs, dict):
        for k in list(inputs.keys()):
            if k in SENSITIVE_INPUT_KEYS:
                inputs[k] = REDACTED

    for text_key in (
        "scenario_description",
        "acceptance_criteria",
        "test_case_content",
        "test_pack_content",
        "regression_content",
        "scenario_name",
    ):
        value = safe.get(text_key)
        if isinstance(value, str) and value:
            safe[text_key] = _scrub_string(value, numbers)

    private = safe.pop("_private", None)
    if private is not None:
        safe["_private"] = REDACTED

    return safe


def redact_text(text: str | None, state: Mapping[str, Any] | None = None) -> str:
    if not text:
        return text or ""
    numbers = _collect_account_numbers(state or {})
    return _scrub_string(text, numbers)
