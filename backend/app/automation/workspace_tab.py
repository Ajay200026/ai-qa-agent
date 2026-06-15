"""Salesforce Lightning workspace tab helpers."""

import logging
import re

from playwright.async_api import Page

from app.automation.combobox import PLACEHOLDER_PATTERNS

logger = logging.getLogger(__name__)

DATA_CHANGE_TAB = re.compile(r"\*?\s*new\s+data\s+change", re.I)

# Shadow-DOM walk: find combobox/input for a form field.
_COMBO_FIND_CORE = """
  const re = new RegExp(placeholderRe, 'i');
  const labelMatch = (t) => {
    if (!labelText) return false;
    const lt = labelText.toLowerCase();
    const s = (t || '').trim().toLowerCase();
    return s === lt || s.startsWith(lt) || (s.length < 80 && s.includes(lt));
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 5) return false;
    const st = window.getComputedStyle(el);
    return st.display !== 'none' && st.visibility !== 'hidden' && parseFloat(st.opacity || '1') > 0;
  };
  const walk = (node) => {
    if (!node) return null;
    const inputs = node.querySelectorAll ? node.querySelectorAll('input:not([type="hidden"])') : [];
    for (const el of inputs) {
      const ph = (el.placeholder || el.getAttribute('aria-label') || '').trim();
      const aria = (el.getAttribute('aria-label') || '').trim();
      if (re.test(ph) || re.test(aria) || labelMatch(ph) || labelMatch(aria)) {
        if (visible(el)) return el;
      }
    }
    const combos = node.querySelectorAll
      ? node.querySelectorAll('[role="combobox"], lightning-combobox, .slds-combobox')
      : [];
    for (const el of combos) {
      const blob = ((el.textContent || '') + ' ' + (el.getAttribute('aria-label') || '')).trim();
      if (re.test(blob) || labelMatch(blob)) {
        if (visible(el)) return el;
      }
    }
    if (labelText) {
      const labels = node.querySelectorAll ? node.querySelectorAll('label, span, div, th') : [];
      for (const lbl of labels) {
        const t = (lbl.textContent || '').trim();
        if (!labelMatch(t)) continue;
        const root = lbl.closest('div, td, fieldset, .slds-form-element, tr') || lbl.parentElement;
        const inp = root && root.querySelector('input:not([type="hidden"]), [role="combobox"], lightning-combobox');
        if (inp && visible(inp)) return inp;
      }
    }
    const kids = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (const el of kids) {
      if (el.shadowRoot) {
        const hit = walk(el.shadowRoot);
        if (hit) return hit;
      }
    }
    return null;
  };
"""

MARK_INPUT_JS = (
    """
({ fieldKey, placeholderRe, labelText }) => {
"""
    + _COMBO_FIND_CORE
    + """
  const el = walk(document);
  if (!el) return false;
  el.setAttribute('data-qa-field', fieldKey);
  el.scrollIntoView({ block: 'center' });
  return true;
}
"""
)

FIELD_PRESENT_JS = (
    """
({ placeholderRe, labelText }) => {
"""
    + _COMBO_FIND_CORE
    + """
  return !!walk(document);
}
"""
)


FIELD_LABELS = {
    "Sales Office": "Sales Office",
    "Customer Number": "Customer Name/Number",
    "Primary Group": "Primary Group",
}


def _data_change_tab_locator(page: Page):
    return page.locator(
        "a[role='tab'], [role='tab'], li.tabs__item a, .slds-tabs__item a, "
        ".slds-context-bar__label, .tabLabel, one-workspace-tab, "
        "span.title, a.tabHeader, [class*='workspaceTab']"
    ).filter(has_text=DATA_CHANGE_TAB)


async def data_change_tab_present(page: Page) -> bool:
    try:
        return await _data_change_tab_locator(page).first.is_visible(timeout=500)
    except Exception:
        return False


async def sales_office_field_present(page: Page) -> bool:
    try:
        return bool(
            await page.evaluate(
                FIELD_PRESENT_JS,
                {
                    "placeholderRe": PLACEHOLDER_PATTERNS["Sales Office"].pattern,
                    "labelText": FIELD_LABELS["Sales Office"],
                },
            )
        )
    except Exception:
        return False


async def data_change_tab_active(page: Page) -> bool:
    try:
        tabs = _data_change_tab_locator(page)
        count = await tabs.count()
        for i in range(count):
            tab = tabs.nth(i)
            if not await tab.is_visible(timeout=300):
                continue
            selected = await tab.get_attribute("aria-selected")
            if selected == "true":
                return True
            is_active = await tab.evaluate(
                """el => {
                  const li = el.closest('li');
                  if (li && /active/i.test(li.className)) return true;
                  return /active/i.test(el.className || '');
                }"""
            )
            if is_active:
                return True
        return False
    except Exception:
        return False


async def _form_visible(page: Page) -> bool:
    """Detect Data Change form — shadow-aware Sales Office field check."""
    if await sales_office_field_present(page):
        return True
    try:
        return await page.get_by_placeholder(PLACEHOLDER_PATTERNS["Sales Office"]).first.is_visible(
            timeout=600
        )
    except Exception:
        return False


async def form_tab_ready(page: Page) -> bool:
    """Data Change form is open — shadow field, header, or workspace tab."""
    if await sales_office_field_present(page):
        return True
    try:
        header = page.get_by_text(re.compile(r"^Data Change$", re.I))
        draft = page.get_by_role("button", name=re.compile(r"save as draft", re.I))
        if await header.first.is_visible(timeout=400) and await draft.first.is_visible(timeout=400):
            return True
    except Exception:
        pass
    if await data_change_tab_present(page):
        return True
    return False


async def find_data_change_page(page: Page) -> Page | None:
    """Return the browser tab that has the Data Change form, if any."""
    for candidate in page.context.pages:
        try:
            if await form_tab_ready(candidate):
                return candidate
        except Exception:
            continue
    return None


async def activate_workspace_tab(page: Page, name_pattern: re.Pattern[str]) -> bool:
    """Click the Lightning workspace tab for the Data Change form (skip if already active)."""
    candidates = [
        page.locator("a[role='tab']").filter(has_text=name_pattern),
        page.get_by_role("tab", name=name_pattern),
        page.locator("li.tabs__item a, .slds-tabs__item a").filter(has_text=name_pattern),
    ]
    for loc in candidates:
        try:
            tabs = loc
            count = await tabs.count()
            for i in range(count):
                tab = tabs.nth(i)
                if not await tab.is_visible(timeout=1000):
                    continue
                text = (await tab.text_content() or "").strip()
                if "queue" in text.lower() and "data change" not in text.lower():
                    continue
                selected = await tab.get_attribute("aria-selected")
                classes = (await tab.get_attribute("class") or "").lower()
                if selected == "true" or "active" in classes or "slds-is-active" in classes:
                    logger.info("Tab already active: %s", text)
                    return True
                await tab.scroll_into_view_if_needed()
                await tab.click(timeout=5000)
                await page.wait_for_timeout(1500)
                logger.info("Activated tab: %s", text)
                return True
        except Exception:
            continue
    return False


async def _resolve_data_change_page(page: Page) -> Page:
    """Find the browser tab that has the Data Change form."""
    found = await find_data_change_page(page)
    if found:
        if found is not page:
            await found.bring_to_front()
            logger.info("Switched to browser tab with Data Change form: %s", found.url)
        return found
    if await data_change_tab_present(page):
        return page
    for other in page.context.pages:
        if other is page:
            continue
        if await data_change_tab_present(other):
            await other.bring_to_front()
            logger.info("Switched to browser tab with Data Change workspace tab: %s", other.url)
            return other
    return page


async def focus_data_change_form(page: Page, *, activate: bool = True) -> Page:
    """Activate the New Data Change workspace tab without flickering browser tabs."""
    page = await _resolve_data_change_page(page)

    if await _form_visible(page):
        logger.info("Data Change form already visible on %s", page.url)
        return page

    if activate and await data_change_tab_present(page):
        if not await data_change_tab_active(page):
            await activate_workspace_tab(page, DATA_CHANGE_TAB)
        for _ in range(12):
            if await _form_visible(page) or await form_tab_ready(page):
                logger.info("Data Change form ready on %s", page.url)
                return page
            await page.wait_for_timeout(500)

    return page
