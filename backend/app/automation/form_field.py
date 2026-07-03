"""Simple form field interaction — find input by placeholder, click, act, verify."""

import asyncio
import logging
import re
from dataclasses import dataclass

from playwright.async_api import Frame, Locator, Page

from app.automation.combobox import is_auto_pick
from app.automation.scope import PageOrFrame, all_scopes
from app.automation.llm_field_agent import llm_assisted_picklist
from app.automation.workspace_tab import (
    FIELD_LABELS,
    FIELD_PRESENT_JS,
    MARK_INPUT_JS,
    _COMBO_FIND_CORE,
    find_data_change_page,
)
from app.core.config import get_settings
from app.knowledge.data_change_field_registry import default_customer_search_query
from app.knowledge.sales_office_rules import (
    choose_office_option,
    office_option_js_pattern,
    resolve_bottler_id,
)

logger = logging.getLogger(__name__)

# One in-browser flow: find combobox in shadow DOM → open → wait → pick → verify.
PICK_COMBOBOX_JS = (
    """
async ({ placeholderRe, labelText, code, pickAny, optionPattern, emptyPattern, preferPrefix }) => {
"""
    + _COMBO_FIND_CORE
    + """
  const optRe = optionPattern ? new RegExp(optionPattern, 'i') : /[SKQ]\\d{3}|Payer|FSV Recipient/i;
  const emptyRe = emptyPattern ? new RegExp(emptyPattern, 'i') : /select sales office|^$/i;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const findInput = () => walk(document);

  const collectNodes = () => {
    const nodes = [];
    const walk = (node) => {
      if (!node) return;
      const kids = node.querySelectorAll ? node.querySelectorAll('*') : [];
      for (const el of kids) nodes.push(el);
      for (const el of kids) {
        if (el.shadowRoot) walk(el.shadowRoot);
      }
    };
    walk(document);
    return nodes;
  };

  const pickVisible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 6 || r.height < 6) return false;
    const st = window.getComputedStyle(el);
    return st.display !== 'none' && st.visibility !== 'hidden' && parseFloat(st.opacity || '1') > 0;
  };

  const clickTriggers = (input) => {
    input.scrollIntoView({ block: 'center', behavior: 'instant' });
    input.focus();
    input.click();

    const roots = [];
    let node = input;
    for (let i = 0; i < 10 && node; i++) {
      const root = node.getRootNode();
      if (root instanceof ShadowRoot) roots.push(root);
      const combo = node.closest?.('[role="combobox"], lightning-base-combobox, .slds-combobox, [class*="combobox"]');
      if (combo && combo !== input) combo.click();
      node = root instanceof ShadowRoot ? root.host : node.parentElement;
    }

    for (const root of roots) {
      for (const sel of [
        'button.slds-input__icon',
        'button[aria-label*="dropdown" i]',
        'button[title*="Open" i]',
        '[part="dropdown-button"]',
        'lightning-icon',
        'button',
      ]) {
        const btns = root.querySelectorAll(sel);
        for (const btn of btns) {
          if (pickVisible(btn)) {
            btn.click();
            return;
          }
        }
      }
    }

    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true, cancelable: true }));
    input.dispatchEvent(new KeyboardEvent('keyup', { key: 'ArrowDown', bubbles: true, cancelable: true }));
  };

  const listOptions = () => {
    const byText = {};
    for (const el of collectNodes()) {
      const role = el.getAttribute?.('role');
      const tag = el.tagName?.toLowerCase() || '';
      if (role !== 'option' && !['div', 'li', 'span', 'a'].includes(tag)) continue;
      const text = (el.textContent || '').trim();
      if (!text || text.length > 80 || !optRe.test(text)) continue;
      if (el.closest('table, thead, th, .slds-table, label')) continue;
      if (!pickVisible(el)) continue;
      const area = el.getBoundingClientRect().width * el.getBoundingClientRect().height;
      if (!byText[text] || area < byText[text].area) byText[text] = { text, area };
    }
    return Object.values(byText)
      .sort((a, b) => a.area - b.area)
      .map((x) => x.text);
  };

  const clickOption = (wantText) => {
    const want = wantText.toLowerCase();
    const officeCode = (wantText.match(/[skq]\\d{3}/i) || [])[0];
    let best = null;
    let bestArea = Infinity;
    for (const el of collectNodes()) {
      const text = (el.textContent || '').trim();
      if (!text) continue;
      const tLower = text.toLowerCase();
      const exact = tLower === want;
      const bySearchCode = code && text.toUpperCase().includes(code.toUpperCase());
      const byOfficeCode = officeCode && text.toUpperCase().includes(officeCode.toUpperCase());
      if (!exact && !bySearchCode && !byOfficeCode) continue;
      if (el.closest('table, thead, th, label')) continue;
      if (!pickVisible(el)) continue;
      const area = el.getBoundingClientRect().width * el.getBoundingClientRect().height;
      if (area < bestArea) {
        best = el;
        bestArea = area;
      }
    }
    if (!best) return false;
    best.scrollIntoView({ block: 'nearest' });
    best.click();
    return true;
  };

  const readValue = (input) => {
    const val = (input.value || input.getAttribute('value') || '').trim();
    if (val && !emptyRe.test(val)) return val;
    const combo = input.closest('[role="combobox"]');
    if (combo) {
      const t = (combo.textContent || '').trim();
      if (t && !emptyRe.test(t)) return t.slice(0, 80);
    }
    return val;
  };

  const input = findInput();
  if (!input) return { ok: false, reason: 'input_not_found' };

  let lastOptions = [];
  for (let attempt = 0; attempt < 2; attempt++) {
    clickTriggers(input);
    let options = [];
    for (let i = 0; i < 8; i++) {
      await sleep(150);
      options = listOptions();
      if (options.length) break;
    }
    lastOptions = options;
    if (!options.length) continue;

    let choice = options[0];
    if (pickAny) {
      const pref = preferPrefix
        ? new RegExp('^' + preferPrefix + '\\d{3}', 'i')
        : /[SKQ]\\d{3}/i;
      const coded = options.filter((o) => pref.test(o));
      if (coded.length) choice = coded[0];
    } else if (code && !pickAny) {
      const match = options.find((o) => o.toUpperCase().includes(code.toUpperCase()));
      if (!match) {
        return { ok: false, reason: 'code_not_found', code, options };
      }
      choice = match;
    }

    if (!clickOption(choice)) continue;
    await sleep(700);

    const selected = readValue(input);
    if (selected && !emptyRe.test(selected)) {
      return { ok: true, choice, selected, options };
    }
    if (choice && !emptyRe.test(choice)) {
      return { ok: true, choice, selected: choice, options };
    }
  }

  return { ok: false, reason: 'dropdown_did_not_open', options: lastOptions };
}
"""
)


COMBO_BBOX_JS = (
    """
({ placeholderRe, labelText }) => {
"""
    + _COMBO_FIND_CORE
    + """
  const el = walk(document);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) };
}
"""
)

LIST_OPTIONS_SHORT_JS = """
({ optionPattern }) => {
  const re = optionPattern ? new RegExp(optionPattern, 'i') : /[SKQ]\\d{3}|Payer|FSV Recipient/i;
  const seen = new Set();
  const walk = (node) => {
    if (!node) return;
    const els = node.querySelectorAll
      ? node.querySelectorAll('[role="option"], .slds-listbox__option, div, li, span')
      : [];
    for (const el of els) {
      const text = (el.textContent || '').trim();
      if (!text || text.length > 80 || !re.test(text)) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 8 || r.height < 8) continue;
      seen.add(text);
    }
    const kids = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (const el of kids) {
      if (el.shadowRoot) walk(el.shadowRoot);
    }
  };
  walk(document);
  return [...seen];
}
"""

CLICK_OPTION_CONTAINS_JS = """
({ text, code }) => {
  const want = (text || '').toLowerCase();
  const codeUp = (code || '').toUpperCase();
  let best = null;
  let bestArea = Infinity;
  const walk = (node) => {
    if (!node) return;
    const els = node.querySelectorAll
      ? node.querySelectorAll('[role="option"], .slds-listbox__option, div, li, span, a')
      : [];
    for (const el of els) {
      const t = (el.textContent || '').trim();
      if (!t || t.length > 80) continue;
      const match = want ? t.toLowerCase() === want : (codeUp && t.toUpperCase().includes(codeUp));
      if (!match) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 8 || r.height < 8) continue;
      const area = r.width * r.height;
      if (area < bestArea) { best = el; bestArea = area; }
    }
    const kids = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (const el of kids) {
      if (el.shadowRoot) walk(el.shadowRoot);
    }
  };
  walk(document);
  if (!best) return false;
  best.click();
  return best.textContent.trim();
}
"""

CUSTOMER_OPTION_CORE = """
  const customerRecordRe = /\\d{6,}\\s*-\\s*\\S+/;
  const skipRe = /^select sales office$|^[SKQ]\\d{3}\\b|Payer|FSV Recipient|^search customer/i;
  const headerBottom = 100;
  const normalizeText = (t) => (t || '').replace(/\\s+/g, ' ').trim();
  const optionVisible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 6) return false;
    if (r.y < headerBottom) return false;
    const st = window.getComputedStyle(el);
    return st.display !== 'none' && st.visibility !== 'hidden' && parseFloat(st.opacity || '1') > 0;
  };
  const inGlobalHeader = (el) => {
    const r = el.getBoundingClientRect();
    if (r.y >= 140) return false;
    return !!el.closest?.('.oneHeader, .slds-global-header, one-app-nav-bar');
  };
  const customerText = (text) => {
    const t = normalizeText(text);
    if (!t || t.length < 10 || t.length > 120 || skipRe.test(t)) return null;
    const m = t.match(customerRecordRe);
    return m ? t : null;
  };
  const optionScore = (el, text) => {
    if (inGlobalHeader(el)) return -1;
    let score = 0;
    if (customerText(text)) score += 50;
    const role = el.getAttribute?.('role') || '';
    const cls = (el.className || '').toString();
    if (role === 'option') score += 40;
    if (cls.includes('slds-listbox__option') || cls.includes('lookup')) score += 30;
    if (el.closest?.('[role="listbox"], .slds-listbox, .slds-dropdown, .slds-lookup, .slds-lookup__menu')) score += 25;
    return score;
  };
  const isCustomerOption = (el, text, anchorRect) => {
    if (!customerText(text)) return false;
    if (inGlobalHeader(el)) return false;
    if (el.closest('thead, th, label, .slds-form-element__label')) return false;
    if (!optionVisible(el)) return false;
    if (anchorRect) {
      const r = el.getBoundingClientRect();
      if (r.y < anchorRect.y - 30) return false;
      if (r.y > anchorRect.y + 400) return false;
    }
    return true;
  };
  const scanForCustomerOption = (node, anchorRect, mode) => {
    if (!node) return mode === 'visible' ? false : null;
    const kids = node.querySelectorAll ? node.querySelectorAll('*') : [];
    let best = null;
    let bestScore = -1;
    for (const el of kids) {
      const text = normalizeText(el.textContent);
      if (text.length < 10 || text.length > 120) {
        if (el.shadowRoot) {
          const hit = scanForCustomerOption(el.shadowRoot, anchorRect, mode);
          if (mode === 'visible' && hit) return true;
          if (mode === 'bbox' && hit && hit.score > bestScore) { best = hit; bestScore = hit.score; }
        }
        continue;
      }
      if (isCustomerOption(el, text, anchorRect)) {
        if (mode === 'visible') return true;
        const score = optionScore(el, text);
        if (score > bestScore) best = { el, text, score };
      }
      if (el.shadowRoot) {
        const hit = scanForCustomerOption(el.shadowRoot, anchorRect, mode);
        if (mode === 'visible' && hit) return true;
        if (mode === 'bbox' && hit && hit.score > bestScore) { best = hit; bestScore = hit.score; }
      }
    }
    return mode === 'visible' ? false : best;
  };
"""

CUSTOMER_LOOKUP_VISIBLE_JS = (
    """
({ placeholderRe, labelText }) => {
"""
    + _COMBO_FIND_CORE
    + CUSTOMER_OPTION_CORE
    + """
  const anchor = walk(document);
  const anchorRect = anchor ? anchor.getBoundingClientRect() : null;
  return !!scanForCustomerOption(document, anchorRect, 'visible');
}
"""
)

FIRST_CUSTOMER_BBOX_JS = (
    """
({ placeholderRe, labelText }) => {
"""
    + _COMBO_FIND_CORE
    + CUSTOMER_OPTION_CORE
    + """
  const anchor = walk(document);
  const anchorRect = anchor ? anchor.getBoundingClientRect() : null;
  const best = scanForCustomerOption(document, anchorRect, 'bbox');
  if (!best) return null;
  const r = best.el.getBoundingClientRect();
  return {
    x: Math.round(r.x + Math.min(r.width * 0.35, 120)),
    y: Math.round(r.y + r.height / 2),
    text: best.text,
  };
}
"""
)

PRIMARY_GROUP_OPTION_CORE = """
  const primaryGroupRe = /[AB]\\d{4}(?:\\s*-\\s*\\S+)?/i;
  const skipRe = /^(select|enter primary|search customer|search\\.\\.\\.|sales office)/i;
  const headerBottom = 100;
  const normalizeText = (t) => (t || '').replace(/\\s+/g, ' ').trim();
  const optionVisible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 6) return false;
    if (r.y < headerBottom) return false;
    const st = window.getComputedStyle(el);
    return st.display !== 'none' && st.visibility !== 'hidden' && parseFloat(st.opacity || '1') > 0;
  };
  const inGlobalHeader = (el) => {
    const r = el.getBoundingClientRect();
    if (r.y >= 140) return false;
    return !!el.closest?.('.oneHeader, .slds-global-header, one-app-nav-bar');
  };
  const primaryGroupText = (text, searchCode) => {
    const t = normalizeText(text);
    if (!t || t.length < 4 || t.length > 120 || skipRe.test(t)) return null;
    if (!primaryGroupRe.test(t)) return null;
    if (searchCode && !t.toUpperCase().includes(String(searchCode).toUpperCase())) return null;
    return t;
  };
  const optionScore = (el, text) => {
    if (inGlobalHeader(el)) return -1;
    let score = 0;
    const role = el.getAttribute?.('role') || '';
    const cls = (el.className || '').toString();
    if (role === 'option') score += 40;
    if (cls.includes('slds-listbox__option') || cls.includes('lookup')) score += 30;
    if (el.closest?.('[role="listbox"], .slds-listbox, .slds-dropdown, .slds-lookup, .slds-lookup__menu')) score += 25;
    if (primaryGroupRe.test(text)) score += 50;
    return score;
  };
  const isPrimaryGroupOption = (el, text, anchorRect, searchCode) => {
    if (!primaryGroupText(text, searchCode)) return false;
    if (inGlobalHeader(el)) return false;
    if (el.closest('thead, th, label, .slds-form-element__label')) return false;
    if (!optionVisible(el)) return false;
    if (anchorRect) {
      const r = el.getBoundingClientRect();
      if (r.y < anchorRect.y - 30) return false;
      if (r.y > anchorRect.y + 400) return false;
    }
    return true;
  };
  const scanForPrimaryGroupOption = (node, anchorRect, searchCode, mode) => {
    if (!node) return mode === 'visible' ? false : null;
    const kids = node.querySelectorAll ? node.querySelectorAll('*') : [];
    let best = null;
    let bestScore = -1;
    for (const el of kids) {
      const text = normalizeText(el.textContent);
      if (text.length < 4 || text.length > 120) {
        if (el.shadowRoot) {
          const hit = scanForPrimaryGroupOption(el.shadowRoot, anchorRect, searchCode, mode);
          if (mode === 'visible' && hit) return true;
          if (mode === 'bbox' && hit && hit.score > bestScore) { best = hit; bestScore = hit.score; }
        }
        continue;
      }
      if (isPrimaryGroupOption(el, text, anchorRect, searchCode)) {
        if (mode === 'visible') return true;
        const score = optionScore(el, text);
        if (score > bestScore) best = { el, text, score };
      }
      if (el.shadowRoot) {
        const hit = scanForPrimaryGroupOption(el.shadowRoot, anchorRect, searchCode, mode);
        if (mode === 'visible' && hit) return true;
        if (mode === 'bbox' && hit && hit.score > bestScore) { best = hit; bestScore = hit.score; }
      }
    }
    return mode === 'visible' ? false : best;
  };
"""

PRIMARY_GROUP_LOOKUP_VISIBLE_JS = (
    """
({ placeholderRe, labelText, searchCode }) => {
"""
    + _COMBO_FIND_CORE
    + PRIMARY_GROUP_OPTION_CORE
    + """
  const anchor = walk(document);
  const anchorRect = anchor ? anchor.getBoundingClientRect() : null;
  return !!scanForPrimaryGroupOption(document, anchorRect, searchCode || '', 'visible');
}
"""
)

FIRST_PRIMARY_GROUP_BBOX_JS = (
    """
({ placeholderRe, labelText, searchCode }) => {
"""
    + _COMBO_FIND_CORE
    + PRIMARY_GROUP_OPTION_CORE
    + """
  const anchor = walk(document);
  const anchorRect = anchor ? anchor.getBoundingClientRect() : null;
  const best = scanForPrimaryGroupOption(document, anchorRect, searchCode || '', 'bbox');
  if (!best) return null;
  const r = best.el.getBoundingClientRect();
  return {
    x: Math.round(r.x + Math.min(r.width * 0.35, 120)),
    y: Math.round(r.y + r.height / 2),
    text: best.text,
  };
}
"""
)

GLOBAL_SEARCH_OPEN_JS = """
() => {
  const walk = (node) => {
    if (!node) return false;
    const text = (node.textContent || '').slice(0, 400);
    if (/recent items|search:\\s*all/i.test(text)) {
      const r = node.getBoundingClientRect?.();
      if (r && r.y < 220 && r.height > 120 && r.width > 280) return true;
    }
    const kids = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (const el of kids) {
      if (el.shadowRoot && walk(el.shadowRoot)) return true;
    }
    return false;
  };
  return walk(document);
}
"""

FORM_CUSTOMER_SEARCH_JS = (
    """
({ placeholderRe, labelText }) => {
"""
    + _COMBO_FIND_CORE
    + """
  const headerBottom = 110;
  const anchor = walk(document);
  const anchorRect = anchor ? anchor.getBoundingClientRect() : null;
  const inGlobalHeader = (el) => {
    const r = el.getBoundingClientRect();
    if (r.y >= 140) return false;
    return !!el.closest?.('.oneHeader, .slds-global-header, one-app-nav-bar');
  };
  const btnVisible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 24 || r.height < 12) return false;
    if (r.y < headerBottom) return false;
    const st = window.getComputedStyle(el);
    return st.display !== 'none' && st.visibility !== 'hidden';
  };
  const walkBtns = (node) => {
    if (!node) return null;
    const els = node.querySelectorAll
      ? node.querySelectorAll('button, lightning-button, [role="button"]')
      : [];
    for (const el of els) {
      const text = (el.textContent || el.getAttribute('title') || el.getAttribute('aria-label') || '').trim();
      if (text.toLowerCase() !== 'search') continue;
      if (inGlobalHeader(el)) continue;
      if (!btnVisible(el)) continue;
      if (anchorRect) {
        const r = el.getBoundingClientRect();
        if (r.y < anchorRect.y - 40) continue;
        if (r.y > anchorRect.y + 500) continue;
      }
      const r = el.getBoundingClientRect();
      return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) };
    }
    const kids = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (const el of kids) {
      if (el.shadowRoot) {
        const hit = walkBtns(el.shadowRoot);
        if (hit) return hit;
      }
    }
    return null;
  };
  return walkBtns(document);
}
"""
)

CLICK_FORM_BUTTON_JS = """
({ label }) => {
  const want = (label || '').toLowerCase();
  const headerBottom = 110;
  const inGlobalHeader = (el) => {
    const r = el.getBoundingClientRect();
    if (r.y >= 140) return false;
    return !!el.closest?.('.oneHeader, .slds-global-header, one-app-nav-bar');
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 24 || r.height < 12) return false;
    if (r.y < headerBottom) return false;
    const st = window.getComputedStyle(el);
    return st.display !== 'none' && st.visibility !== 'hidden';
  };
  const walk = (node) => {
    if (!node) return null;
    const els = node.querySelectorAll
      ? node.querySelectorAll('button, lightning-button, [role="button"]')
      : [];
    for (const el of els) {
      const text = (el.textContent || el.getAttribute('title') || el.getAttribute('aria-label') || '').trim();
      if (text.toLowerCase() !== want) continue;
      if (inGlobalHeader(el)) continue;
      if (!visible(el)) continue;
      el.scrollIntoView({ block: 'center', behavior: 'instant' });
      const r = el.getBoundingClientRect();
      return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) };
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
  return walk(document);
}
"""


@dataclass(frozen=True)
class FormFieldSpec:
    placeholder: re.Pattern[str]
    empty_values: frozenset[str] = frozenset()


FORM_FIELDS: dict[str, FormFieldSpec] = {
    "Sales Office": FormFieldSpec(
        placeholder=re.compile(r"select sales office", re.I),
        empty_values=frozenset({"", "select sales office"}),
    ),
    "Customer Number": FormFieldSpec(
        placeholder=re.compile(r"search customer", re.I),
        empty_values=frozenset({"", "search customer...", "search customer"}),
    ),
    "Primary Group": FormFieldSpec(
        placeholder=re.compile(r"enter primary group|primary group", re.I),
        empty_values=frozenset(
            {"", "select primary group", "search...", "enter primary group", "enter primary"}
        ),
    ),
}


async def _scope_page(scope: PageOrFrame) -> Page:
    return scope if isinstance(scope, Page) else scope.page


async def field_present(scope: PageOrFrame, field_key: str) -> bool:
    spec = FORM_FIELDS[field_key]
    label = FIELD_LABELS.get(field_key)
    try:
        return bool(
            await scope.evaluate(
                FIELD_PRESENT_JS,
                {"placeholderRe": spec.placeholder.pattern, "labelText": label},
            )
        )
    except Exception:
        return False


async def resolve_form_scope(
    page: Page,
    field_key: str = "Sales Office",
    *,
    prefer_page: Page | None = None,
) -> PageOrFrame:
    """Find the frame with the target field on the current Data Change tab only."""
    from app.automation.scope import all_scopes

    active = prefer_page if prefer_page and not prefer_page.is_closed() else page
    if active is not page:
        page = active

    for scope in all_scopes(page):
        try:
            if await field_present(scope, field_key):
                return scope
        except Exception:
            continue

    if prefer_page is not None:
        return page

    found_page = await find_data_change_page(page)
    if found_page and found_page is not page:
        await found_page.bring_to_front()
        page = found_page
        for scope in all_scopes(page):
            try:
                if await field_present(scope, field_key):
                    return scope
            except Exception:
                continue

    return page


async def find_input(scope: PageOrFrame, field_key: str) -> Locator:
    spec = FORM_FIELDS[field_key]
    label = FIELD_LABELS.get(field_key)
    field_attr = field_key.replace(" ", "_")

    try:
        marked = scope.locator(f'[data-qa-field="{field_attr}"]').first
        if await marked.is_visible(timeout=800):
            return marked
    except Exception:
        pass

    if await field_present(scope, field_key):
        await scope.evaluate(
            MARK_INPUT_JS,
            {
                "fieldKey": field_attr,
                "placeholderRe": spec.placeholder.pattern,
                "labelText": label,
            },
        )
        try:
            marked = scope.locator(f'[data-qa-field="{field_attr}"]').first
            await marked.wait_for(state="visible", timeout=3000)
            return marked
        except Exception:
            pass

    for loc in (
        scope.get_by_placeholder(spec.placeholder),
        scope.locator(f'input[placeholder*="Sales Office" i]') if field_key == "Sales Office" else None,
        scope.locator(f'input[placeholder*="Search customer" i]') if field_key == "Customer Number" else None,
        scope.locator(f'input[placeholder*="Primary Group" i]') if field_key == "Primary Group" else None,
    ):
        if loc is None:
            continue
        try:
            inp = loc.first
            if await inp.is_visible(timeout=3000):
                if await inp.evaluate("el => el.tagName.toLowerCase()") == "input":
                    return inp
        except Exception:
            continue

    if label:
        try:
            inp = (
                scope.locator("div, td, .slds-form-element")
                .filter(has=scope.get_by_text(label, exact=False))
                .locator("input:not([type='hidden'])")
                .first
            )
            if await inp.is_visible(timeout=2000):
                return inp
        except Exception:
            pass

    marked = await scope.evaluate(
        MARK_INPUT_JS,
        {
            "fieldKey": field_attr,
            "placeholderRe": spec.placeholder.pattern,
            "labelText": label,
        },
    )
    if marked:
        inp = scope.locator(f'[data-qa-field="{field_attr}"]').first
        await inp.wait_for(state="visible", timeout=5000)
        return inp

    raise RuntimeError(
        f"Sales Office field not visible — open the '* New Data Change' tab first"
        if field_key == "Sales Office"
        else f"Could not find input for '{field_key}'"
    )


async def _customer_field_payload(field_key: str) -> dict:
    spec = FORM_FIELDS[field_key]
    label = FIELD_LABELS.get(field_key)
    return {"placeholderRe": spec.placeholder.pattern, "labelText": label}


async def dismiss_global_search(scope: PageOrFrame) -> None:
    """Close Salesforce global search overlay only if it is open (not customer lookup)."""
    try:
        if await scope.evaluate(GLOBAL_SEARCH_OPEN_JS):
            await scope.keyboard.press("Escape")
            await scope.wait_for_timeout(350)
    except Exception:
        pass


async def customer_lookup_visible(scope: PageOrFrame, field_key: str = "Customer Number") -> bool:
    try:
        payload = await _customer_field_payload(field_key)
        if await scope.evaluate(CUSTOMER_LOOKUP_VISIBLE_JS, payload):
            return True
    except Exception:
        pass
    # Playwright text fallback for lookup rows like "0500931141 - ZETT BUILDING MAINTENANCE"
    try:
        row = scope.get_by_text(re.compile(r"\d{6,}\s*-\s*\S+")).first
        if await row.is_visible(timeout=600):
            box = await row.bounding_box()
            if box and box["y"] > 100:
                return True
    except Exception:
        pass
    return False


async def _mouse_click_first_customer(
    scope: PageOrFrame, field_key: str = "Customer Number"
) -> str | None:
    """Mouse-click the customer lookup row (e.g. '0500931141 - ZETT BUILDING MAINTENANCE')."""
    payload = await _customer_field_payload(field_key)
    bbox = await scope.evaluate(FIRST_CUSTOMER_BBOX_JS, payload)
    if not bbox:
        return None
    x, y = int(bbox["x"]), int(bbox["y"])
    await scope.mouse.click(x, y)
    await scope.wait_for_timeout(600)
    text = str(bbox.get("text") or "").strip()
    logger.info("Mouse-clicked customer lookup row: %s", text)
    return text or None


async def _keyboard_pick_first_customer(scope: PageOrFrame, field_key: str) -> str | None:
    """ArrowDown + Enter on the customer lookup input."""
    try:
        inp = await find_input(scope, field_key)
        await inp.focus()
        await scope.keyboard.press("ArrowDown")
        await scope.wait_for_timeout(250)
        await scope.keyboard.press("Enter")
        await scope.wait_for_timeout(500)
        value = await _input_value(inp)
        if value and not re.fullmatch(r"0?\d{2,3}", value):
            return value
    except Exception as exc:
        logger.debug("Keyboard customer pick failed: %s", exc)
    return None


async def _customer_selected(scope: PageOrFrame, field_key: str, typed: str) -> bool:
    # Dropdown still open means the row was not confirmed yet.
    if await customer_lookup_visible(scope, field_key):
        return False
    try:
        inp = await find_input(scope, field_key)
        value = await _input_value(inp)
        if not value or value.lower() in ("search customer...", "search customer"):
            return False
        typed = (typed or "").strip()
        # Confirmed pick shows "NUMBER - NAME" or a longer account number.
        if re.search(r"\d{6,}\s*-\s*.+", value):
            return True
        if typed and value == typed:
            return False
        if typed and value.startswith(typed) and len(value) <= len(typed):
            return False
        return len(value) >= 7 or " - " in value
    except Exception:
        return False


async def click_form_button(scope: PageOrFrame, label: str) -> None:
    """Click a labeled form button (Submit, Save Draft, etc.) inside shadow DOM."""
    hit = await scope.evaluate(CLICK_FORM_BUTTON_JS, {"label": label})
    if hit:
        await scope.mouse.click(int(hit["x"]), int(hit["y"]))
        await scope.wait_for_timeout(400)
        logger.info("Clicked '%s' button via shadow DOM", label)
        return

    pattern = re.compile(rf"^{re.escape(label)}$", re.I)
    for candidate in (
        scope.get_by_role("button", name=pattern),
        scope.locator("button, lightning-button").filter(has_text=pattern),
    ):
        try:
            btn = candidate.first
            if await btn.is_visible(timeout=2000):
                await btn.scroll_into_view_if_needed()
                await btn.click(timeout=5000)
                logger.info("Clicked '%s' button via Playwright", label)
                return
        except Exception:
            continue
    raise RuntimeError(f"'{label}' button not found on form")


async def click_search_button(scope: PageOrFrame, field_key: str = "Customer Number") -> bool:
    """Click the Data Change form Search button near the customer field (not global search)."""
    await dismiss_global_search(scope)
    payload = await _customer_field_payload(field_key)
    hit = await scope.evaluate(FORM_CUSTOMER_SEARCH_JS, payload)
    if hit:
        await scope.mouse.click(int(hit["x"]), int(hit["y"]))
        await scope.wait_for_timeout(500)
        logger.info("Clicked form Search button near customer field")
        return True

    logger.info(
        "No form Search button near customer field — proceeding after customer selection"
    )
    return False


async def _input_value(inp: Locator) -> str:
    try:
        return (await inp.input_value() or "").strip()
    except Exception:
        return (await inp.text_content() or "").strip()


async def _mouse_pick_combobox(
    scope: PageOrFrame,
    field_key: str,
    value: str | None,
    payload: dict,
) -> str | None:
    """Fast path: mouse-click combobox center, poll options, click match."""
    list_payload = {"optionPattern": payload.get("optionPattern")}
    bbox = await scope.evaluate(
        COMBO_BBOX_JS,
        {"placeholderRe": payload["placeholderRe"], "labelText": payload["labelText"]},
    )
    if not bbox:
        return None

    x, y = int(bbox["x"]), int(bbox["y"])
    bottler_id = payload.get("bottlerId")
    for click_x in (x, x + 35):
        await scope.mouse.click(click_x, y)
        await scope.wait_for_timeout(300)
        options: list[str] = []
        for _ in range(8):
            raw = await scope.evaluate(LIST_OPTIONS_SHORT_JS, list_payload)
            options = [str(o).strip() for o in (raw or []) if str(o).strip()]
            if options:
                break
            await scope.wait_for_timeout(150)
        if not options:
            continue

        try:
            choice = choose_office_option(
                options,
                value,
                bottler_id=bottler_id if field_key == "Sales Office" else None,
            )
        except ValueError:
            raise RuntimeError(
                f"{field_key} '{value}' not found. Available: {', '.join(options)}"
            ) from None

        picked = await scope.evaluate(
            CLICK_OPTION_CONTAINS_JS,
            {"text": choice, "code": code if field_key == "Primary Group" else ""},
        )
        if picked:
            logger.info("Mouse picklist '%s': %s", field_key, picked)
            return str(picked)
    return None


async def _pick_combobox(
    scope: PageOrFrame,
    field_key: str,
    value: str | None,
    *,
    bottler_id: str | None = None,
) -> str:
    spec = FORM_FIELDS[field_key]
    label = FIELD_LABELS.get(field_key)
    code = None if is_auto_pick(value) else (value or "").strip().upper()
    empty_pattern = "|".join(re.escape(v) for v in spec.empty_values if v) or "select|^$"
    resolved_bottler = resolve_bottler_id(bottler_id=bottler_id) if field_key == "Sales Office" else None
    prefer_prefix = ""
    option_pattern: str | None = None
    if field_key == "Sales Office":
        from app.knowledge.sales_office_rules import office_prefix_for_bottler

        prefer_prefix = office_prefix_for_bottler(resolved_bottler) or ""
        option_pattern = office_option_js_pattern(resolved_bottler)
    elif field_key == "Primary Group":
        option_pattern = re.escape(code) if code else r"[AB]\\d{4}"
    payload = {
        "placeholderRe": spec.placeholder.pattern,
        "labelText": label,
        "code": code or "",
        "pickAny": is_auto_pick(value),
        "optionPattern": option_pattern,
        "emptyPattern": empty_pattern,
        "preferPrefix": prefer_prefix,
        "bottlerId": resolved_bottler,
    }

    if field_key == "Primary Group" and code:
        inp = await find_input(scope, field_key)
        await inp.click(timeout=5000)
        await inp.fill(code)
        await scope.wait_for_timeout(600)

    if not await field_present(scope, field_key):
        raise RuntimeError(
            f"{field_key} field not visible — open the '* New Data Change' tab first"
        )

    try:
        result = await scope.evaluate(PICK_COMBOBOX_JS, payload)
        if result and result.get("ok"):
            choice = result.get("choice") or result.get("selected") or ""
            logger.info("Picklist '%s': picked=%s", field_key, choice)
            return choice
        if result and result.get("reason") == "code_not_found":
            options = result.get("options") or []
            raise RuntimeError(
                f"{field_key} '{value}' not found. Available: {', '.join(options)}"
            )
    except RuntimeError:
        raise
    except Exception as exc:
        logger.debug("Picklist JS failed: %s", exc)

    try:
        mouse_choice = await _mouse_pick_combobox(scope, field_key, value, payload)
        if mouse_choice:
            return mouse_choice
    except RuntimeError:
        raise
    except Exception as exc:
        logger.debug("Mouse picklist failed: %s", exc)

    settings = get_settings()
    if settings.llm_field_fallback:
        logger.info("Trying LLM fallback for '%s' (slow)", field_key)
        page = await _scope_page(scope)
        try:
            picked = await asyncio.wait_for(
                llm_assisted_picklist(
                    page,
                    label or field_key,
                    value,
                    pick_any=is_auto_pick(value),
                ),
                timeout=25,
            )
            if picked:
                return picked
        except asyncio.TimeoutError:
            logger.warning("LLM picklist timed out for '%s'", field_key)
        except Exception as exc:
            logger.warning("LLM picklist failed: %s", exc)

    raise RuntimeError(
        f"{field_key} dropdown did not open. Click the field manually to confirm options appear."
    )


async def _primary_group_field_payload(search_code: str = "") -> dict:
    spec = FORM_FIELDS["Primary Group"]
    label = FIELD_LABELS.get("Primary Group")
    return {
        "placeholderRe": spec.placeholder.pattern,
        "labelText": label,
        "searchCode": search_code,
    }


async def primary_group_lookup_visible(
    scope: PageOrFrame, search_code: str = ""
) -> bool:
    try:
        payload = await _primary_group_field_payload(search_code)
        if await scope.evaluate(PRIMARY_GROUP_LOOKUP_VISIBLE_JS, payload):
            return True
    except Exception:
        pass
    if search_code:
        try:
            row = scope.get_by_text(re.compile(re.escape(search_code), re.I)).first
            if await row.is_visible(timeout=400):
                box = await row.bounding_box()
                if box and box["y"] > 100:
                    return True
        except Exception:
            pass
    return False


async def _mouse_click_primary_group_row(
    scope: PageOrFrame, search_code: str = ""
) -> str | None:
    payload = await _primary_group_field_payload(search_code)
    bbox = await scope.evaluate(FIRST_PRIMARY_GROUP_BBOX_JS, payload)
    if not bbox:
        return None
    x, y = int(bbox["x"]), int(bbox["y"])
    await scope.mouse.click(x, y)
    await scope.wait_for_timeout(600)
    text = str(bbox.get("text") or "").strip()
    logger.info("Mouse-clicked Primary Group search row: %s", text)
    return text or None


async def _keyboard_pick_primary_group(
    scope: PageOrFrame, search_code: str
) -> str | None:
    try:
        inp = await find_input(scope, "Primary Group")
        await inp.focus()
        await scope.keyboard.press("ArrowDown")
        await scope.wait_for_timeout(250)
        await scope.keyboard.press("Enter")
        await scope.wait_for_timeout(500)
        value = await _input_value(inp)
        if value and await _primary_group_selected(scope, search_code):
            return value
    except Exception as exc:
        logger.debug("Keyboard Primary Group pick failed: %s", exc)
    return None


async def _primary_group_selected(scope: PageOrFrame, code: str) -> bool:
    """True when the Primary Group search field shows a confirmed selection."""
    if await primary_group_lookup_visible(scope, code):
        return False
    try:
        inp = await find_input(scope, "Primary Group")
        value = (await _input_value(inp) or "").strip()
        if len(value) < 4:
            return False
        if not re.search(r"[AB]\d{4}", value, re.I):
            return False
        target = (code or "").strip().upper()
        if not target:
            return True
        return target in value.upper()
    except Exception:
        return False


async def search_primary_group(scope: PageOrFrame, value: str) -> str:
    """Primary Group is a search field: type code, wait for results, click row."""
    query = (value or "").strip()
    if is_auto_pick(query):
        query = "A"

    if await _primary_group_selected(scope, query):
        inp = await find_input(scope, "Primary Group")
        current = await _input_value(inp)
        logger.info("Primary Group search already set: %s", current)
        return current

    await dismiss_global_search(scope)

    for attempt in range(8):
        if await primary_group_lookup_visible(scope, query):
            picked = await _mouse_click_primary_group_row(scope, query)
            await scope.wait_for_timeout(400)
            if await _primary_group_selected(scope, query):
                inp = await find_input(scope, "Primary Group")
                return await _input_value(inp)
            picked = await _keyboard_pick_primary_group(scope, query)
            if picked:
                logger.info("Primary Group search selected via keyboard: %s", picked)
                return picked

        if attempt == 0 or not await primary_group_lookup_visible(scope, query):
            inp = await find_input(scope, "Primary Group")
            await inp.click(timeout=5000)
            await inp.fill(query)
            await scope.wait_for_timeout(900)

        await scope.wait_for_timeout(400)

    if await _primary_group_selected(scope, query):
        inp = await find_input(scope, "Primary Group")
        return await _input_value(inp)

    raise RuntimeError(
        f"Could not select Primary Group '{value}' from search results — "
        "type in the search field and pick a row like 'A0168-DESCRIPTION'"
    )


async def set_primary_group(scope: PageOrFrame, value: str) -> str:
    """Alias for search_primary_group — Primary Group is never a picklist."""
    return await search_primary_group(scope, value)


async def click_picklist(
    scope: PageOrFrame,
    field_key: str,
    value: str | None = None,
    *,
    bottler_id: str | None = None,
) -> str:
    """Click combobox → wait for options → pick → verify."""
    return await _pick_combobox(scope, field_key, value, bottler_id=bottler_id)


async def type_in_input(scope: PageOrFrame, field_key: str, text: str) -> str:
    inp = await find_input(scope, field_key)
    await inp.click(timeout=5000)
    await inp.fill(text)
    await scope.wait_for_timeout(400)
    return await _input_value(inp)


async def click_lookup(scope: PageOrFrame, field_key: str, query: str | None = None) -> str:
    if field_key == "Primary Group":
        return await search_primary_group(scope, query or "")

    typed = "060" if is_auto_pick(query) else (query or "060")

    if await _customer_selected(scope, field_key, typed):
        inp = await find_input(scope, field_key)
        value = await _input_value(inp)
        logger.info("Lookup '%s' already selected: %s", field_key, value)
        return value

    for attempt in range(5):
        if await customer_lookup_visible(scope, field_key):
            picked = await _mouse_click_first_customer(scope, field_key)
            await scope.wait_for_timeout(400)
            if await _customer_selected(scope, field_key, typed):
                logger.info("Lookup '%s' selected: %s", field_key, picked or "")
                inp = await find_input(scope, field_key)
                return await _input_value(inp)
            picked = await _keyboard_pick_first_customer(scope, field_key)
            if picked and await _customer_selected(scope, field_key, typed):
                logger.info("Lookup '%s' selected via keyboard: %s", field_key, picked)
                return picked

        if attempt == 0 and not await customer_lookup_visible(scope, field_key):
            inp = await find_input(scope, field_key)
            await inp.click(timeout=5000)
            await inp.fill(typed)
            await scope.wait_for_timeout(900)

        await scope.wait_for_timeout(400)

    if await _customer_selected(scope, field_key, typed):
        inp = await find_input(scope, field_key)
        return await _input_value(inp)

    raise RuntimeError(
        f"Could not select customer from dropdown for '{field_key}' — "
        "click the row like '0500931141 - CUSTOMER NAME' did not stick"
    )
