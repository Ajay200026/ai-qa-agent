"""Shared helpers for Salesforce Lightning combobox / picklist / lookup fields."""

import re

from playwright.async_api import Locator

from app.automation.scope import PageOrFrame

AUTO_PICK = "__any__"
AUTO_PICK_ALIASES = frozenset({AUTO_PICK, "any", "first", "*", "default", ""})

# Visible containers for custom + SLDS dropdown menus (excludes data tables).
DROPDOWN_CONTAINER_SELECTORS = (
    ".slds-dropdown:not(.slds-hide)",
    ".slds-dropdown.slds-is-open",
    "[class*='dropdown-menu']:visible",
    "[class*='Dropdown']:visible",
    ".slds-popover:visible",
    "ul[class*='menu']:visible",
)

FIELD_LABEL_ALIASES: dict[str, tuple[str, ...]] = {
    "Customer Number": ("Customer Name/Number", "Customer Number"),
    "Sales Office": ("Sales Office",),
    "Primary Group": ("Primary Group",),
}

PLACEHOLDER_PATTERNS: dict[str, re.Pattern[str]] = {
    "Sales Office": re.compile(r"select sales office", re.I),
    "Customer Number": re.compile(r"search customer", re.I),
    "Primary Group": re.compile(r"select.*primary|primary group", re.I),
}


def is_auto_pick(value: str | None) -> bool:
    if value is None:
        return True
    return value.strip().lower() in AUTO_PICK_ALIASES


def _labels_for_field(label: str) -> tuple[str, ...]:
    return FIELD_LABEL_ALIASES.get(label, (label,))


def combobox_candidates(scope: PageOrFrame, label: str) -> list[Locator]:
    pattern = re.compile(re.escape(label), re.I)
    return [
        scope.get_by_role("combobox", name=pattern),
        scope.get_by_label(label),
        scope.locator("lightning-combobox").filter(has_text=pattern).locator("input, button"),
        scope.locator("lightning-base-combobox").filter(has_text=pattern).locator("input, button"),
        scope.locator(".slds-combobox").filter(has_text=pattern).locator("input, button"),
        scope.locator(f'[data-field-label*="{label}" i] input, [data-field-label*="{label}" i] button'),
    ]


def native_select_candidates(scope: PageOrFrame, label: str) -> list[Locator]:
    pattern = re.compile(re.escape(label), re.I)
    return [
        scope.locator("select").filter(has=scope.get_by_label(label)),
        scope.locator(".slds-form-element").filter(has_text=pattern).locator("select"),
        scope.locator("label").filter(has_text=pattern).locator("xpath=following-sibling::select[1]"),
        scope.locator("label").filter(has_text=pattern).locator("..").locator("select"),
        scope.get_by_label(label).locator("xpath=ancestor::td[1]/following-sibling::td//select"),
        scope.locator(f"select[title*='{label}' i], select[aria-label*='{label}' i]"),
        scope.locator("tr").filter(has_text=pattern).locator("select"),
        scope.locator("th").filter(has_text=pattern).locator("xpath=following-sibling::td//select"),
    ]


def salesforce_field_candidates(scope: PageOrFrame, label: str) -> list[Locator]:
    """Broad field lookup for Lightning + Visualforce table/modal forms."""
    pattern = re.compile(re.escape(label), re.I)
    loose = re.compile(label.replace(" ", r"\s+"), re.I)
    candidates: list[Locator] = []
    candidates.extend(combobox_candidates(scope, label))
    candidates.extend(native_select_candidates(scope, label))
    candidates.extend([
        scope.get_by_label(label, exact=False),
        scope.get_by_text(loose, exact=True),
        scope.locator(
            "th, label, span.slds-form-element__label, .slds-form-element__legend, abbr"
        ).filter(has_text=pattern),
        scope.locator(".slds-form-element, .slds-form-element__control, .slds-grid")
        .filter(has_text=pattern)
        .locator("input:not([type='hidden']), button, select, lightning-base-combobox"),
        scope.locator("tr, .slds-form__row").filter(has_text=pattern).locator(
            "input:not([type='hidden']), button, select, .slds-combobox__input, "
            "lightning-base-combobox input, lightning-base-combobox button"
        ),
        scope.locator("lightning-input-field, lightning-combobox, lightning-record-edit-form")
        .filter(has_text=pattern)
        .locator("input, button, select"),
        scope.locator(f"[data-field-label*='{label}' i], [data-target-selection-name*='{label}' i]"),
    ])
    return candidates


def field_interaction_targets(scope: PageOrFrame, label: str) -> list[Locator]:
    """Visible <input> for a form field — placeholder only (no label/text divs)."""
    candidates: list[Locator] = []
    for alias in _labels_for_field(label):
        ph = PLACEHOLDER_PATTERNS.get(label) or PLACEHOLDER_PATTERNS.get(alias)
        if ph:
            candidates.append(scope.get_by_placeholder(ph))
            candidates.append(scope.locator(f"input[placeholder*='{alias}' i]"))
    return candidates


def menu_option_candidates(scope: PageOrFrame, option: str) -> list[Locator]:
    """New (+) menu items — scoped to dropdowns, not queue table rows."""
    pattern = re.compile(re.escape(option), re.I)
    table = scope.locator("table, .slds-table, [role='grid']")
    candidates: list[Locator] = [
        scope.get_by_role("menuitem", name=pattern),
        scope.get_by_role("option", name=pattern),
    ]
    for container_sel in DROPDOWN_CONTAINER_SELECTORS:
        container = scope.locator(container_sel)
        candidates.append(container.get_by_text(option, exact=True))
        candidates.append(container.locator("a, li, span, div, button").filter(has_text=pattern))
    candidates.append(
        scope.locator(
            "[role='menuitem'], [role='option'], .slds-dropdown__item a, "
            "lightning-menu-item a, a[data-label]"
        ).filter(has_text=pattern)
    )
    # Text match excluding table/grid rows (module column shows "New Data Change").
    candidates.append(
        scope.get_by_text(option, exact=True).filter(has_not=table)
    )
    candidates.append(
        scope.get_by_text(pattern).filter(has_not=table)
    )
    return candidates


def sales_office_click_targets(scope: PageOrFrame) -> list[Locator]:
    return field_interaction_targets(scope, "Sales Office")


def listbox_option_candidates(scope: PageOrFrame, *, text: str | None = None) -> list[Locator]:
    return dropdown_option_candidates(scope, text=text)


def dropdown_option_candidates(scope: PageOrFrame, *, text: str | None = None) -> list[Locator]:
    """Options in open picklist — SLDS listbox, native ul/li, custom div menus."""
    pattern = re.compile(re.escape(text), re.I) if text else None
    scoped = scope.locator("[role='listbox']:visible")
    if pattern:
        return [
            scoped.get_by_role("option", name=pattern),
            scoped.locator("[role='option']").filter(has_text=pattern),
            scope.locator(".slds-listbox__option:visible").filter(has_text=pattern),
            scope.locator("lightning-base-combobox-item:visible").filter(has_text=pattern),
            scope.locator("ul:visible li, .dropdown-item:visible, [class*='option']:visible")
            .filter(has_text=pattern),
            scope.locator("div[role='option']:visible").filter(has_text=pattern),
        ]
    return [
        scoped.locator("[role='option']").first,
        scope.locator(".slds-listbox__option:visible").first,
        scope.locator("lightning-base-combobox-item:visible").first,
        scope.locator("ul:visible li").first,
        scope.locator(".dropdown-item:visible, [class*='option']:visible").first,
        scope.locator("div[role='option']:visible").first,
    ]
