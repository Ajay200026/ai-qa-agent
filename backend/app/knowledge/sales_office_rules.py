"""Bottler-aware Sales Office picklist rules.

Office code prefixes differ by bottler:
- 5000 Northeast → S###
- 4900 Abarta    → Q###
- 4600 Reyes     → K###

Special offices (valid selections, not headers):
- Payer
- FSV Recipient
"""

from __future__ import annotations

import re

from app.automation.combobox import is_auto_pick
from app.knowledge.customer_search_rules import FSV_RECIPIENT_OFFICE, PAYER_OFFICE

BOTTLER_OFFICE_PREFIX: dict[str, str] = {
    "5000": "S",
    "4900": "Q",
    "4600": "K",
}

ALL_OFFICE_PREFIXES = "SKQ"
SPECIAL_OFFICES = frozenset({PAYER_OFFICE, FSV_RECIPIENT_OFFICE})


def resolve_bottler_id(
    *,
    bottler_id: str | None = None,
    step_params: dict | None = None,
    org=None,
    customer_target: dict | None = None,
) -> str | None:
    for src in (
        bottler_id,
        (step_params or {}).get("bottler_id"),
        (step_params or {}).get("bottler"),
        (customer_target or {}).get("bottler"),
        getattr(org, "bottler", None) if org is not None else None,
    ):
        if src is not None and str(src).strip():
            return str(src).strip()
    return None


def office_prefix_for_bottler(bottler_id: str | None) -> str | None:
    if not bottler_id:
        return None
    return BOTTLER_OFFICE_PREFIX.get(str(bottler_id).strip())


def office_option_pattern(bottler_id: str | None) -> re.Pattern[str]:
    prefix = office_prefix_for_bottler(bottler_id)
    if prefix:
        return re.compile(
            rf"{prefix}\d{{3}}|{re.escape(PAYER_OFFICE)}|{re.escape(FSV_RECIPIENT_OFFICE)}",
            re.I,
        )
    return re.compile(
        rf"[{ALL_OFFICE_PREFIXES}]\d{{3}}|{re.escape(PAYER_OFFICE)}|{re.escape(FSV_RECIPIENT_OFFICE)}",
        re.I,
    )


def office_option_js_pattern(bottler_id: str | None) -> str:
    prefix = office_prefix_for_bottler(bottler_id)
    if prefix:
        return f"{prefix}\\d{{3}}|{PAYER_OFFICE}|{FSV_RECIPIENT_OFFICE}"
    return f"[{ALL_OFFICE_PREFIXES}]\\d{{3}}|{PAYER_OFFICE}|{FSV_RECIPIENT_OFFICE}"


def office_option_full_js_pattern(bottler_id: str | None) -> str:
    prefix = office_prefix_for_bottler(bottler_id)
    coded = (
        f"{prefix}\\d{{3}}\\s+[\\w\\s,]+"
        if prefix
        else f"[{ALL_OFFICE_PREFIXES}]\\d{{3}}\\s+[\\w\\s,]+"
    )
    return f"{coded}|^{PAYER_OFFICE}$|^{FSV_RECIPIENT_OFFICE}$"


def office_code_pattern_js(bottler_id: str | None) -> str:
    prefix = office_prefix_for_bottler(bottler_id)
    if prefix:
        return f"{prefix}\\d{{3}}"
    return f"[{ALL_OFFICE_PREFIXES.lower()}]\\d{{3}}"


def is_special_office(text: str) -> bool:
    return (text or "").strip().lower() in {o.lower() for o in SPECIAL_OFFICES}


def is_coded_office(text: str, bottler_id: str | None = None) -> bool:
    prefix = office_prefix_for_bottler(bottler_id)
    if prefix:
        return bool(re.search(rf"\b{prefix}\d{{3}}\b", text or "", re.I))
    return bool(re.search(rf"[{ALL_OFFICE_PREFIXES}]\d{{3}}", text or "", re.I))


def rank_office_options(options: list[str], bottler_id: str | None) -> list[str]:
    """Prefer bottler-coded offices; keep Payer / FSV Recipient as valid fallbacks."""
    prefix = office_prefix_for_bottler(bottler_id)
    primary: list[str] = []
    other_coded: list[str] = []
    specials: list[str] = []
    rest: list[str] = []

    for option in options:
        text = (option or "").strip()
        if not text:
            continue
        if is_special_office(text):
            specials.append(text)
        elif prefix and re.search(rf"\b{prefix}\d{{3}}\b", text, re.I):
            primary.append(text)
        elif is_coded_office(text):
            other_coded.append(text)
        else:
            rest.append(text)

    return primary + other_coded + rest + specials


def choose_office_option(
    options: list[str],
    value: str | None,
    *,
    bottler_id: str | None = None,
) -> str:
    if not options:
        raise ValueError("No sales office options available")

    if value and not is_auto_pick(value):
        wanted = value.strip().lower()
        for option in options:
            ol = option.lower()
            if wanted in ol or ol.startswith(wanted[:4]):
                return option
        available = ", ".join(options)
        raise ValueError(f"Sales office '{value}' not found. Available: {available}")

    ranked = rank_office_options(options, bottler_id)
    return ranked[0]
