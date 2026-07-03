"""Smart field resolver — detects Salesforce Lightning field types via DOM probe."""

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from playwright.async_api import Locator, Page
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.combobox import (
    dropdown_option_candidates,
    field_interaction_targets,
    is_auto_pick,
    native_select_candidates,
    salesforce_field_candidates,
)
from app.automation.picklist_interaction import click_field_control, open_picklist, pick_option
from app.automation.scope import PageOrFrame, all_scopes, find_visible_in_scopes
from app.knowledge.data_change_field_registry import get_field_by_label, resolve_automation_type

logger = logging.getLogger(__name__)

DOM_PROBE_JS = """
(label) => {
  const norm = (s) => (s || '').trim().toLowerCase();
  const target = norm(label);

  const addCandidate = (el, type) => {
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) return null;
    const tag = el.tagName.toLowerCase();
    if (tag === 'select') return { type: 'select', selector: null, tag };
    const id = el.id || '';
    const testId = el.getAttribute('data-testid') || '';
    const aria = el.getAttribute('aria-label') || '';
    let selector = null;
    if (testId) selector = `[data-testid="${testId}"]`;
    else if (id) selector = `#${CSS.escape(id)}`;
    else if (aria) selector = `[aria-label="${aria.replace(/"/g, '\\\\"')}"]`;
    return { type, selector, tag };
  };

  document.querySelectorAll('label, .slds-form-element__label, legend, th').forEach(lbl => {
    const text = norm(lbl.textContent);
    if (!text.includes(target) && !target.includes(text)) return;
    const root = lbl.closest('.slds-form-element, lightning-input, lightning-combobox, lightning-textarea, fieldset, tr') || lbl.parentElement;
    if (!root) return;

    const nativeSelect = root.querySelector('select') || (lbl.tagName === 'LABEL' && lbl.htmlFor ? document.getElementById(lbl.htmlFor) : null);
    if (nativeSelect && nativeSelect.tagName.toLowerCase() === 'select') {
      const hit = addCandidate(nativeSelect, 'select');
      if (hit) { window.__sf_probe_hit = hit; return; }
    }

    const combo = root.querySelector('lightning-combobox, [role="combobox"], input[role="combobox"]');
    if (combo) {
      const hit = addCandidate(combo.querySelector('input, button') || combo, 'combobox');
      if (hit) { window.__sf_probe_hit = hit; return; }
    }

    const lookup = root.querySelector('lightning-input-field, input[type="search"], [part="input"]');
    if (lookup) {
      const hit = addCandidate(lookup, 'lookup');
      if (hit) { window.__sf_probe_hit = hit; return; }
    }

    const textInput = root.querySelector('input:not([type="hidden"]), textarea, lightning-input input');
    if (textInput) {
      const hit = addCandidate(textInput, 'text');
      if (hit) { window.__sf_probe_hit = hit; return; }
    }
  });

  document.querySelectorAll(`[aria-label*="${label}" i], [placeholder*="${label}" i], select[title*="${label}" i]`).forEach(el => {
    const tag = el.tagName.toLowerCase();
    if (tag === 'select') {
      window.__sf_probe_hit = { type: 'select', selector: null, tag: 'select' };
      return;
    }
    if (tag === 'input' || tag === 'textarea') {
      const t = el.type || 'text';
      const type = el.getAttribute('role') === 'combobox' || el.closest('lightning-combobox') ? 'combobox' : (t === 'search' ? 'lookup' : 'text');
      const hit = addCandidate(el, type);
      if (hit) window.__sf_probe_hit = hit;
    }
  });

  return window.__sf_probe_hit || null;
}
"""


@dataclass
class ResolvedField:
    field_name: str
    field_type: str
    selector: str | None
    locator: Locator | None = None
    scope: PageOrFrame | None = None


class SmartFieldResolver:
    def __init__(
        self,
        page: Page,
        template_key: str,
        db: AsyncSession | None = None,
    ):
        self.page = page
        self.template_key = template_key
        self.db = db
        self._repo = None
        if db:
            from app.repositories.workflow_repository import WorkflowRepository

            self._repo = WorkflowRepository(db)

    def _build_field_locators(self, field_name: str):
        def builder(scope: PageOrFrame) -> list[Locator]:
            return field_interaction_targets(scope, field_name)

        return builder

    async def resolve(self, field_name: str, hint_type: str | None = None) -> ResolvedField:
        registry_hint = resolve_automation_type(field_name, hint_type or "combobox")
        hint_type = registry_hint
        meta = get_field_by_label(field_name)
        if meta and meta.label and meta.label != field_name:
            field_name = meta.label
        if self._repo:
            cached = await self._repo.get_field_registry(self.template_key, field_name)
            if cached and cached.locator_hints:
                for hint in cached.locator_hints:
                    for scope in all_scopes(self.page):
                        try:
                            loc = scope.locator(hint["selector"]).first
                            if await loc.is_visible(timeout=2000):
                                return ResolvedField(
                                    field_name=field_name,
                                    field_type=cached.field_type,
                                    selector=hint["selector"],
                                    locator=loc,
                                    scope=scope,
                                )
                        except Exception:
                            continue

        found = await find_visible_in_scopes(
            all_scopes(self.page),
            self._build_field_locators(field_name),
            per_locator_ms=500,
        )
        if found:
            scope, locator = found
            field_type = hint_type or "combobox"
            try:
                tag = await locator.first.evaluate("el => el.tagName.toLowerCase()")
                if tag == "select":
                    field_type = "select"
            except Exception:
                pass
            return ResolvedField(
                field_name=field_name,
                field_type=field_type,
                selector=None,
                locator=locator,
                scope=scope,
            )

        for scope in all_scopes(self.page):
            try:
                await scope.evaluate("() => { window.__sf_probe_hit = null; }")
                probe = await scope.evaluate(DOM_PROBE_JS, field_name)
            except Exception:
                continue
            if not probe:
                continue
            field_type = probe.get("type") or hint_type or "text"
            selector = probe.get("selector")
            if field_type == "select":
                native = await find_visible_in_scopes(
                    [scope],
                    lambda s: native_select_candidates(s, field_name),
                    per_locator_ms=500,
                )
                if native:
                    _, locator = native
                    return ResolvedField(
                        field_name=field_name,
                        field_type="select",
                        selector=None,
                        locator=locator,
                        scope=scope,
                    )
            if selector:
                locator = scope.locator(selector).first
                try:
                    await locator.wait_for(state="visible", timeout=3000)
                except Exception:
                    locator = scope.get_by_label(field_name, exact=False).first
                await self._persist(field_name, field_type, selector)
                return ResolvedField(
                    field_name=field_name,
                    field_type=field_type,
                    selector=selector,
                    locator=locator,
                    scope=scope,
                )

        fallback_scope = self.page
        fallback = self.page.get_by_label(re.compile(re.escape(field_name), re.I)).first
        return ResolvedField(
            field_name=field_name,
            field_type=hint_type or "combobox",
            selector=None,
            locator=fallback,
            scope=fallback_scope,
        )

    async def _persist(self, field_name: str, field_type: str, selector: str) -> None:
        if not self._repo:
            return
        try:
            await self._repo.upsert_field_registry(
                self.template_key,
                field_name,
                field_type,
                [{"selector": selector, "verified_at": datetime.now(UTC).isoformat()}],
            )
            await self._repo.db.commit()
        except Exception as exc:
            logger.debug("Could not persist field registry: %s", exc)


class FieldActions:
    """Typed interactions based on resolved field type."""

    def __init__(self, page: Page, resolver: SmartFieldResolver, check_cancelled=None):
        self.page = page
        self.resolver = resolver
        self._check_cancelled = check_cancelled or (lambda: None)

    def _scope(self, resolved: ResolvedField) -> PageOrFrame:
        return resolved.scope or self.page

    async def set_field(self, field_name: str, value: str | None, hint_type: str | None = None) -> str:
        resolved = await self.resolver.resolve(field_name, hint_type)
        self._check_cancelled()
        if resolved.field_type == "select":
            return await self.set_native_select(resolved, value)
        match resolved.field_type:
            case "combobox":
                return await self.set_combobox(resolved, value)
            case "lookup":
                return await self.set_lookup(resolved, value)
            case "toggle":
                return await self.set_toggle(resolved, value)
            case _:
                return await self.set_text(resolved, value or "")

    async def set_native_select(self, resolved: ResolvedField, value: str | None) -> str:
        scope = self._scope(resolved)
        loc = resolved.locator or scope.get_by_label(resolved.field_name)
        await loc.first.wait_for(state="visible", timeout=8000)
        if is_auto_pick(value):
            options = loc.locator("option")
            count = await options.count()
            for i in range(count):
                opt = options.nth(i)
                val = (await opt.get_attribute("value") or "").strip()
                text = (await opt.text_content() or "").strip()
                if val and text and text.lower() not in {"--none--", "select", ""}:
                    await loc.first.select_option(value=val)
                    return text
            if count > 1:
                await loc.first.select_option(index=1)
                return (await options.nth(1).text_content() or "").strip()
            raise RuntimeError(f"No selectable options in '{resolved.field_name}'")
        try:
            await loc.first.select_option(label=value)
            return value or ""
        except Exception:
            await loc.first.select_option(value=value)
            return value or ""

    async def _click_field_target(self, scope: PageOrFrame, loc: Locator) -> Locator:
        target = loc.first
        tag = "unknown"
        try:
            tag = await target.evaluate("el => el.tagName.toLowerCase()")
        except Exception:
            pass

        if tag in {"th", "label", "span", "abbr", "div"}:
            row_input = target.locator(
                "xpath=ancestor::tr[1]//input[not(@type='hidden')] | "
                "ancestor::tr[1]//button | ancestor::tr[1]//select | "
                "following-sibling::td[1]//input | following-sibling::td[1]//button | "
                "following-sibling::td[1]//select | "
                "ancestor::div[contains(@class,'slds-form-element')][1]//input | "
                "ancestor::div[contains(@class,'slds-form-element')][1]//button | "
                "ancestor::div[contains(@class,'slds-form-element')][1]//select"
            ).first
            try:
                if await row_input.is_visible(timeout=2000):
                    target = row_input
            except Exception:
                pass

        await click_field_control(scope, target)
        return target

    async def _pick_dropdown_option(self, scope: PageOrFrame, value: str | None) -> str:
        return await pick_option(scope, value)

    async def _verify_field_updated(self, target: Locator, selected: str) -> None:
        try:
            current = (await target.input_value() or "").strip()
            if current and current.lower() not in {"select", "search customer...", "select sales office"}:
                return
        except Exception:
            pass
        try:
            parent_text = (await target.locator("xpath=ancestor::*[contains(@class,'slds-form-element')][1]").text_content() or "").strip()
            if selected and selected.lower() in parent_text.lower():
                return
        except Exception:
            pass

    async def set_combobox(self, resolved: ResolvedField, value: str | None) -> str:
        scope = self._scope(resolved)
        loc = resolved.locator
        if not loc:
            found = await find_visible_in_scopes(
                all_scopes(self.page),
                lambda s: field_interaction_targets(s, resolved.field_name),
                per_locator_ms=600,
            )
            if not found:
                raise RuntimeError(f"Could not find combobox field '{resolved.field_name}'")
            scope, loc = found

        target = await self._click_field_target(scope, loc)
        await open_picklist(scope, target)
        selected = await self._pick_dropdown_option(scope, value)
        await self._verify_field_updated(target, selected)
        return selected

    async def set_lookup(self, resolved: ResolvedField, value: str | None) -> str:
        if resolved.field_name == "Primary Group":
            from app.automation.form_field import resolve_form_scope, search_primary_group

            page = self.page
            scope = await resolve_form_scope(page, "Primary Group")
            return await search_primary_group(scope, value or "")

        scope = self._scope(resolved)
        loc = resolved.locator
        if not loc:
            found = await find_visible_in_scopes(
                all_scopes(self.page),
                lambda s: field_interaction_targets(s, resolved.field_name),
                per_locator_ms=600,
            )
            if not found:
                raise RuntimeError(f"Could not find lookup field '{resolved.field_name}'")
            scope, loc = found

        target = await self._click_field_target(scope, loc)
        if is_auto_pick(value):
            await target.fill("a")
            await scope.wait_for_timeout(700)
        elif value:
            await target.fill(value)
            await scope.wait_for_timeout(600)
        await open_picklist(scope, target)
        selected = await self._pick_dropdown_option(
            scope, None if is_auto_pick(value) else value
        )
        await self._verify_field_updated(target, selected)
        return selected

    async def set_text(self, resolved: ResolvedField, value: str) -> str:
        scope = self._scope(resolved)
        loc = resolved.locator or scope.get_by_label(resolved.field_name)
        await loc.first.click(timeout=5000)
        await loc.first.fill(value)
        return value

    async def set_toggle(self, resolved: ResolvedField, value: str | None) -> str:
        scope = self._scope(resolved)
        loc = resolved.locator or scope.get_by_label(resolved.field_name)
        want_on = str(value).lower() in {"true", "on", "yes", "1", "enabled"}
        try:
            checked = await loc.first.is_checked()
        except Exception:
            checked = False
        if want_on != checked:
            await loc.first.click(timeout=3000)
        return "on" if want_on else "off"
