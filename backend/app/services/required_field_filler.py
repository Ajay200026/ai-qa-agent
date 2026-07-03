"""Auto-fill empty required Data Change fields before / after submit."""

from __future__ import annotations

import logging

from playwright.async_api import Page

from app.automation.combobox import is_auto_pick
from app.automation.field_resolver import FieldActions
from app.automation.field_state import get_field_value
from app.automation.form_validation import is_empty_field_value
from app.knowledge.data_change_field_registry import (
    get_field_by_label,
    get_required_fields_for_bottler,
    resolve_automation_type,
    section_to_tab_label,
)

logger = logging.getLogger(__name__)


async def fill_missing_fields(
    page: Page,
    field_labels: list[str],
    *,
    bottler_id: str,
    field_actions: FieldActions,
    data_change_page,
    db=None,
) -> list[str]:
    """Open the right tabs and auto-pick values for empty required fields."""
    if not field_labels:
        return []

    logs: list[str] = []
    by_section: dict[str, list[str]] = {}
    for label in field_labels:
        meta = get_field_by_label(label)
        section = meta.section if meta else ""
        by_section.setdefault(section, []).append(meta.label if meta else label)

    for section, labels in by_section.items():
        tab = section_to_tab_label(section)
        if tab:
            await data_change_page.open_form_tab(tab)

        for label in labels:
            try:
                current = await get_field_value(page, label, db)
            except Exception:
                current = ""
            meta = get_field_by_label(label)
            if not is_empty_field_value(current, meta.placeholder if meta else None):
                continue

            field_type = resolve_automation_type(label, "combobox")
            try:
                result = await field_actions.set_field(label, "__any__", field_type)
                logs.append(f"Auto-filled required field: {label} = {result}")
                logger.info("Auto-filled required field %s = %s", label, result)
            except Exception as exc:
                logger.warning("Could not auto-fill required field %s: %s", label, exc)
                if not is_auto_pick(label):
                    logs.append(f"Auto-fill failed for {label}: {exc}")

    return logs


async def fill_empty_required_for_bottler(
    page: Page,
    *,
    bottler_id: str,
    field_actions: FieldActions,
    data_change_page,
    db=None,
) -> list[str]:
    """Pre-submit pass: fill all registry-required empty fields for this bottler."""
    from app.automation.form_validation import scan_empty_required_fields

    missing = await scan_empty_required_fields(page, bottler_id, db=db)
    if not missing:
        return []
    return await fill_missing_fields(
        page,
        missing,
        bottler_id=bottler_id,
        field_actions=field_actions,
        data_change_page=data_change_page,
        db=db,
    )
