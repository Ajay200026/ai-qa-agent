"""Click-to-open and pick for custom Salesforce / Visualforce picklists."""

import logging
import re

from playwright.async_api import Locator

from app.automation.combobox import PLACEHOLDER_PATTERNS, dropdown_option_candidates, is_auto_pick
from app.automation.scope import PageOrFrame

logger = logging.getLogger(__name__)

OPTION_EXCLUDE_PATTERN = re.compile(
    r"search by|request id|my request|cancel request|module|account group|"
    r"select sales office|search customer|save as draft|submit|data change",
    re.I,
)

# e.g. "K003 West Dundee", "FSV Recipient"
SALES_OFFICE_OPTION_TEXT = re.compile(r"K\d{3}\s+[\w\s]+|^FSV Recipient$", re.I)

SHADOW_WALK_JS = """
(root) => {
  const out = [];
  const walk = (node) => {
    if (!node) return;
    if (node.querySelectorAll) {
      node.querySelectorAll('input, button, div, li, span, a, [role="option"], [role="combobox"]').forEach(el => out.push(el));
    }
    const children = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (const el of children) {
      if (el.shadowRoot) walk(el.shadowRoot);
    }
  };
  walk(root || document);
  return out;
}
"""

CLICK_SALES_OFFICE_JS = """
() => {
  const walk = (node) => {
    if (!node) return null;
    const inputs = node.querySelectorAll ? node.querySelectorAll('input, [role="combobox"]') : [];
    for (const el of inputs) {
      const ph = (el.placeholder || el.getAttribute('aria-label') || '').toLowerCase();
      if (ph.includes('select sales office')) {
        const r = el.getBoundingClientRect();
        if (r.width > 20 && r.height > 5) {
          el.scrollIntoView({block: 'center'});
          el.focus();
          el.click();
          return el;
        }
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
  return !!walk(document);
}
"""

HAS_OPTIONS_JS = """
({ pattern }) => {
  const re = pattern ? new RegExp(pattern, 'i') : /K\\d{3}|FSV Recipient/i;
  const walk = (node, hits) => {
    if (!node) return;
    const els = node.querySelectorAll ? node.querySelectorAll('div, li, span, a, [role="option"]') : [];
    for (const el of els) {
      const text = (el.textContent || '').trim();
      if (!text || text.length > 80) continue;
      if (!re.test(text)) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 8 || r.height < 8) continue;
      const st = window.getComputedStyle(el);
      if (st.display === 'none' || st.visibility === 'hidden' || st.opacity === '0') continue;
      hits.push(text);
    }
    const kids = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (const el of kids) {
      if (el.shadowRoot) walk(el.shadowRoot, hits);
    }
  };
  const hits = [];
  walk(document, hits);
  return hits.length ? hits[0] : null;
}
"""

# Walk all DOM (incl. shadow roots) and click the Sales Office input/combobox.
OPEN_SALES_OFFICE_JS = """
() => {
  const nodes = [];
  const walk = (node) => {
    if (!node) return;
    const kids = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (const el of kids) nodes.push(el);
    for (const el of kids) { if (el.shadowRoot) walk(el.shadowRoot); }
  };
  walk(document);

  let input = null;
  for (const el of nodes) {
    const tag = el.tagName ? el.tagName.toLowerCase() : '';
    const isField = tag === 'input' || (el.getAttribute && el.getAttribute('role') === 'combobox');
    if (!isField) continue;
    const ph = (el.placeholder || el.getAttribute('aria-label') || '').toLowerCase();
    if (ph.includes('sales office')) {
      const r = el.getBoundingClientRect();
      if (r.width > 15 && r.height > 5) { input = el; break; }
    }
  }
  if (!input) {
    for (const el of nodes) {
      const t = (el.textContent || '').trim().toLowerCase();
      if (t === 'sales office') {
        const c = el.closest('div, td, fieldset') || el.parentElement;
        const inp = c && c.querySelector('input, [role="combobox"]');
        if (inp) { input = inp; break; }
      }
    }
  }
  if (!input) return { ok: false, reason: 'input_not_found' };

  input.scrollIntoView({ block: 'center' });
  input.focus();
  input.click();
  const trig = input.closest('[role="combobox"], .slds-combobox, [class*="combobox"], [class*="dropdown"]');
  if (trig && trig !== input) trig.click();
  return { ok: true };
}
"""

# Return visible option texts (strings only) matching Sales Office pattern.
LIST_SALES_OFFICE_OPTIONS_JS = """
() => {
  const optionRe = /(^|\\s)K\\d{3}(\\s|$)|FSV Recipient/i;
  const nodes = [];
  const walk = (node) => {
    if (!node) return;
    const kids = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (const el of kids) nodes.push(el);
    for (const el of kids) { if (el.shadowRoot) walk(el.shadowRoot); }
  };
  walk(document);

  const byText = {};
  for (const el of nodes) {
    const tag = el.tagName ? el.tagName.toLowerCase() : '';
    const role = el.getAttribute && el.getAttribute('role');
    if (!['div','li','span','a'].includes(tag) && role !== 'option') continue;
    const text = (el.textContent || '').trim();
    if (!text || text.length > 60) continue;
    if (!optionRe.test(text)) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 10 || r.height < 8) continue;
    const st = window.getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden' || st.opacity === '0') continue;
    const area = r.width * r.height;
    if (!byText[text] || area < byText[text]) byText[text] = area;
  }
  // sort by area asc (smallest = leaf clickable)
  return Object.keys(byText).sort((a, b) => byText[a] - byText[b]);
}
"""

# Click the option whose text matches (exact-ish), smallest element wins.
CLICK_SALES_OFFICE_OPTION_JS = """
(wantText) => {
  const want = (wantText || '').toLowerCase();
  const nodes = [];
  const walk = (node) => {
    if (!node) return;
    const kids = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (const el of kids) nodes.push(el);
    for (const el of kids) { if (el.shadowRoot) walk(el.shadowRoot); }
  };
  walk(document);

  let best = null;
  let bestArea = Infinity;
  for (const el of nodes) {
    const tag = el.tagName ? el.tagName.toLowerCase() : '';
    const role = el.getAttribute && el.getAttribute('role');
    if (!['div','li','span','a'].includes(tag) && role !== 'option') continue;
    const text = (el.textContent || '').trim();
    if (!text || text.length > 60) continue;
    if (text.toLowerCase() !== want) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 10 || r.height < 8) continue;
    const st = window.getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden') continue;
    const area = r.width * r.height;
    if (area < bestArea) { best = el; bestArea = area; }
  }
  if (!best) return false;
  best.scrollIntoView({ block: 'nearest' });
  best.click();
  return true;
}
"""

PICK_OPTION_JS = """
({ pattern, pickFirst }) => {
  const re = pattern ? new RegExp(pattern, 'i') : /K\\d{3}\\s+[\\w\\s]+|^FSV Recipient$/i;
  const walk = (node, hits) => {
    if (!node) return;
    const els = node.querySelectorAll ? node.querySelectorAll('div, li, span, a, [role="option"]') : [];
    for (const el of els) {
      const text = (el.textContent || '').trim();
      if (!text || text.length > 80) continue;
      if (!re.test(text)) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 8 || r.height < 8) continue;
      const st = window.getComputedStyle(el);
      if (st.display === 'none' || st.visibility === 'hidden' || st.opacity === '0') continue;
      hits.push({ text, area: r.width * r.height, el });
    }
    const kids = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (const el of kids) {
      if (el.shadowRoot) walk(el.shadowRoot, hits);
    }
  };
  const hits = [];
  walk(document, hits);
  if (!hits.length) return null;
  hits.sort((a, b) => a.area - b.area);
  const choice = pickFirst ? hits[0] : hits.find(h => h.text.length < 60) || hits[0];
  choice.el.scrollIntoView({block: 'nearest'});
  choice.el.click();
  return choice.text;
}
"""


def sales_office_input_candidates(scope: PageOrFrame) -> list[Locator]:
    ph = PLACEHOLDER_PATTERNS["Sales Office"]
    return [
        scope.get_by_placeholder(ph),
        scope.locator("input[placeholder*='Sales Office' i]"),
        scope.get_by_role("combobox", name=re.compile(r"sales office", re.I)),
        scope.locator("label, span, div")
        .filter(has_text=re.compile(r"^Sales Office$", re.I))
        .locator("xpath=ancestor::*[self::div or self::td][1]//input[not(@type='hidden')]"),
    ]


def sales_office_option_candidates(scope: PageOrFrame, *, text: str | None = None) -> list[Locator]:
    if text and not is_auto_pick(text):
        pattern = re.compile(re.escape(text), re.I)
        return [
            scope.get_by_text(pattern),
            scope.locator("div, li, span, a, [role='option']").filter(has_text=pattern),
        ]
    return [
        scope.get_by_text(SALES_OFFICE_OPTION_TEXT),
        scope.locator("div, li, span, a, [role='option']")
        .filter(has_text=SALES_OFFICE_OPTION_TEXT)
        .filter(has_not=scope.locator("table, thead, th, label")),
    ]


def popup_option_candidates(scope: PageOrFrame, *, text: str | None = None) -> list[Locator]:
    pattern = re.compile(re.escape(text), re.I) if text else None
    if pattern:
        return [
            scope.get_by_text(pattern).filter(has_not=scope.locator("table thead, th, label")),
            scope.locator("div, li, span, a, [role='option']").filter(has_text=pattern),
        ]
    return [
        scope.locator(
            "[role='option']:visible, .slds-listbox__option:visible, "
            "lightning-base-combobox-item:visible, ul:visible li"
        ).filter(has_not=scope.locator("table thead, table th")),
    ]


def all_option_candidates(scope: PageOrFrame, *, text: str | None = None) -> list[Locator]:
    candidates = dropdown_option_candidates(scope, text=text)
    candidates.extend(popup_option_candidates(scope, text=text))
    return candidates


def _dropdown_triggers(root: Locator, target: Locator) -> list[Locator]:
    return [
        target,
        root.locator(
            "button, [aria-haspopup], [class*='chevron'], [class*='arrow'], "
            "[class*='dropdown'], svg, .slds-input__icon, [class*='icon']"
        ),
        target.locator(
            "xpath=following-sibling::* | ../button | ../span | ../div//button | "
            "../..//*[contains(@class,'arrow') or contains(@class,'chevron') or "
            "contains(@class,'icon')]"
        ),
    ]


async def _try_click(loc: Locator) -> bool:
    try:
        el = loc.first
        if not await el.is_visible(timeout=800):
            return False
        await el.scroll_into_view_if_needed()
        try:
            await el.click(timeout=2000)
        except Exception:
            await el.click(force=True, timeout=2000)
        return True
    except Exception:
        return False


async def click_right_edge(scope: PageOrFrame, target: Locator) -> bool:
    try:
        box = await target.first.bounding_box()
        if not box or box["width"] < 20:
            return False
        x = box["x"] + box["width"] - 8
        y = box["y"] + box["height"] / 2
        await scope.mouse.click(x, y)
        return True
    except Exception:
        return False


async def click_field_control(scope: PageOrFrame, target: Locator) -> None:
    root = target.locator(
        "xpath=ancestor::*[contains(@class,'form') or contains(@class,'field') or "
        "contains(@class,'combobox') or self::td or self::tr or self::div][1]"
    )
    for trigger in _dropdown_triggers(root, target):
        if await _try_click(trigger):
            await scope.wait_for_timeout(300)
            return
    if await click_right_edge(scope, target):
        await scope.wait_for_timeout(300)
        return
    try:
        await target.first.focus(timeout=1000)
    except Exception:
        await target.first.click(force=True, timeout=2000)


async def _options_visible(scope: PageOrFrame, extra: list[Locator] | None = None) -> bool:
    locators = list(extra or []) + all_option_candidates(scope)
    for candidate in locators:
        try:
            if await candidate.first.is_visible(timeout=300):
                txt = (await candidate.first.text_content() or "").strip()
                if txt and not OPTION_EXCLUDE_PATTERN.search(txt):
                    return True
        except Exception:
            continue
    try:
        found = await scope.evaluate(
            HAS_OPTIONS_JS, {"pattern": r"K\d{3}\s+[\w\s]+|^FSV Recipient$"}
        )
        return bool(found)
    except Exception:
        return False


async def _list_sales_office_options(scope: PageOrFrame) -> list[str]:
    try:
        opts = await scope.evaluate(LIST_SALES_OFFICE_OPTIONS_JS)
        return [str(o).strip() for o in (opts or []) if str(o).strip()]
    except Exception:
        return []


async def select_sales_office_value(scope: PageOrFrame, value: str | None) -> str:
    """Open Sales Office dropdown and pick an option, fully via shadow-aware JS.

    Tries Playwright click first, then JS open. Polls for options, logs what it
    finds, and clicks the chosen option by exact text via JS.
    """
    last_diag = ""

    for attempt in range(3):
        opened_js = False
        try:
            res = await scope.evaluate(OPEN_SALES_OFFICE_JS)
            opened_js = bool(res and res.get("ok"))
            if res and not res.get("ok"):
                last_diag = res.get("reason", "")
        except Exception as exc:
            last_diag = f"open_js_error:{exc}"

        if not opened_js:
            for loc in sales_office_input_candidates(scope):
                try:
                    target = loc.first
                    if await target.is_visible(timeout=1500):
                        await target.scroll_into_view_if_needed()
                        await target.click(timeout=2500)
                        opened_js = True
                        break
                except Exception:
                    continue

        await scope.wait_for_timeout(600)

        options: list[str] = []
        for _ in range(8):
            options = await _list_sales_office_options(scope)
            if options:
                break
            await scope.wait_for_timeout(300)

        if not options:
            logger.warning("Sales Office: no options after open (attempt %d, diag=%s)", attempt + 1, last_diag)
            await scope.wait_for_timeout(400)
            continue

        logger.info("Sales Office options found (%d): %s", len(options), options[:8])

        target_text = options[0]
        if value and not is_auto_pick(value):
            wanted = value.strip().lower()
            match = next((o for o in options if wanted in o.lower()), None)
            target_text = match or options[0]

        try:
            clicked = await scope.evaluate(CLICK_SALES_OFFICE_OPTION_JS, target_text)
            if clicked:
                logger.info("Selected sales office: %s", target_text)
                return target_text
        except Exception as exc:
            last_diag = f"click_option_error:{exc}"

        try:
            opt = scope.get_by_text(target_text, exact=True).first
            await opt.click(timeout=3000)
            logger.info("Selected sales office (locator): %s", target_text)
            return target_text
        except Exception as exc:
            last_diag = f"locator_click_error:{exc}"

    raise RuntimeError(
        f"No dropdown options appeared after clicking the field (diag={last_diag})"
    )


async def open_sales_office_dropdown(scope: PageOrFrame) -> Locator:
    await scope.evaluate(OPEN_SALES_OFFICE_JS)
    return scope.get_by_placeholder(PLACEHOLDER_PATTERNS["Sales Office"])


async def pick_sales_office(scope: PageOrFrame, value: str | None) -> str:
    return await select_sales_office_value(scope, value)


async def open_picklist(scope: PageOrFrame, target: Locator) -> None:
    for attempt in range(4):
        await click_field_control(scope, target)
        await scope.wait_for_timeout(400)
        if await _options_visible(scope):
            logger.info("Picklist opened (attempt %d)", attempt + 1)
            return
        try:
            await target.first.focus(timeout=1000)
            await scope.keyboard.press("ArrowDown")
            await scope.wait_for_timeout(400)
            if await _options_visible(scope):
                return
        except Exception:
            pass
        await scope.wait_for_timeout(300)
    raise RuntimeError("No dropdown options appeared after clicking the field")


async def pick_option(scope: PageOrFrame, value: str | None, *, timeout_ms: int = 10_000) -> str:
    pick = None if is_auto_pick(value) else value
    elapsed = 0
    while elapsed < timeout_ms:
        for candidate in all_option_candidates(scope, text=pick):
            try:
                opt = candidate.first
                if not await opt.is_visible(timeout=500):
                    continue
                text = (await opt.text_content() or "").strip()
                if not text or OPTION_EXCLUDE_PATTERN.search(text):
                    continue
                if pick and pick.lower() not in text.lower():
                    continue
                await opt.click(timeout=3000)
                return text
            except Exception:
                continue
        await scope.wait_for_timeout(300)
        elapsed += 300

    selects = scope.locator("select")
    count = await selects.count()
    for i in range(count):
        try:
            sel = selects.nth(i)
            if not await sel.is_visible(timeout=300):
                continue
            if is_auto_pick(value):
                opts = sel.locator("option")
                n = await opts.count()
                for j in range(n):
                    val = (await opts.nth(j).get_attribute("value") or "").strip()
                    txt = (await opts.nth(j).text_content() or "").strip()
                    if val and txt.lower() not in {"--none--", "select", ""}:
                        await sel.select_option(value=val)
                        return txt
            else:
                await sel.select_option(label=value)
                return value or ""
        except Exception:
            continue

    raise RuntimeError("No dropdown options appeared after clicking the field")
