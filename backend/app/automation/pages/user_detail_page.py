"""Salesforce Setup → User detail page (Login As / impersonation)."""

from __future__ import annotations

import logging
import re

from playwright.async_api import Locator

from app.automation.pages.base_page import BasePage
from app.automation.scope import PageOrFrame, all_scopes, find_visible_in_scopes

logger = logging.getLogger(__name__)

_LOGIN_PATTERN = re.compile(r"^\s*(Login|Login As)\s*$", re.IGNORECASE)
_USER_DETAIL_PATTERN = re.compile(r"User Detail", re.IGNORECASE)
_SEARCH_PLACEHOLDER = re.compile(r"search", re.IGNORECASE)


class UserDetailPageError(RuntimeError):
    """Raised when navigation or interaction with the User detail page fails."""


def lightning_base_url(instance_url: str) -> str:
    """Derive Lightning host from stored org instance URL."""
    url = (instance_url or "").strip().rstrip("/")
    if not url:
        return ""
    if ".lightning.force.com" in url:
        return url
    if ".my.salesforce.com" in url:
        host = url.split("//", 1)[-1]
        prefix = host.replace(".my.salesforce.com", "")
        return f"https://{prefix}.lightning.force.com"
    if ".salesforce.com" in url:
        host = url.split("//", 1)[-1]
        prefix = host.split(".")[0]
        return f"https://{prefix}.lightning.force.com"
    return url


def build_manage_users_url(instance_url: str, user_id: str) -> str:
    """Setup User detail URL used for Login As."""
    base = lightning_base_url(instance_url)
    if not base:
        raise UserDetailPageError("Missing instance_url for User detail navigation")
    return f"{base}/lightning/setup/ManageUsers/page?address=/{user_id}"


def build_classic_user_detail_url(instance_url: str, user_id: str) -> str:
    """Classic setup User detail URL (has Login button outside Lightning record view)."""
    base = (instance_url or "").strip().rstrip("/")
    if not base:
        raise UserDetailPageError("Missing instance_url for User detail navigation")
    return f"{base}/{user_id}?noredirect=1&isUserEntityOverride=1"


def pick_global_search_terms(user_name: str | None, username: str | None) -> list[str]:
    """Terms to try in Lightning global search (display name first, then login email)."""
    terms: list[str] = []
    for value in (user_name, username):
        cleaned = (value or "").strip()
        if cleaned and cleaned not in terms:
            terms.append(cleaned)
    return terms


def is_lightning_user_record_url(url: str) -> bool:
    lower = (url or "").lower()
    return "/lightning/r/user/" in lower


def _login_button_locators(scope: PageOrFrame) -> list[Locator]:
    return [
        scope.get_by_role("button", name=_LOGIN_PATTERN),
        scope.get_by_role("link", name=_LOGIN_PATTERN),
        scope.locator('input[name="login"][value="Login"]'),
        scope.locator('input[name="login"]'),
        scope.locator('a:has-text("Login")'),
        scope.locator('button:has-text("Login")'),
        scope.locator('a:has-text("Login As")'),
        scope.locator('button:has-text("Login As")'),
    ]


def _user_detail_locators(scope: PageOrFrame) -> list[Locator]:
    return [
        scope.get_by_role("button", name=_USER_DETAIL_PATTERN),
        scope.get_by_role("link", name=_USER_DETAIL_PATTERN),
        scope.locator('button:has-text("User Detail")'),
        scope.locator('a:has-text("User Detail")'),
    ]


def _global_search_input_locators(scope: PageOrFrame) -> list[Locator]:
    return [
        scope.get_by_placeholder(_SEARCH_PLACEHOLDER),
        scope.locator('input[type="search"]'),
        scope.locator('button[title="Search"]'),
        scope.get_by_role("button", name=re.compile(r"^Search$", re.IGNORECASE)),
        scope.locator(".forceSearchInput input"),
        scope.locator("lightning-input input"),
    ]


def _global_search_result_locators(scope: PageOrFrame, search_text: str, user_id: str) -> list[Locator]:
    pattern = re.compile(re.escape(search_text), re.IGNORECASE)
    uid = user_id[:15] if len(user_id) > 15 else user_id
    return [
        scope.locator(f'a[href*="{user_id}"]'),
        scope.locator(f'a[href*="{uid}"]'),
        scope.get_by_role("option", name=pattern),
        scope.get_by_role("link", name=pattern),
        scope.locator("one-search-panel").get_by_text(search_text, exact=False),
        scope.locator(".forceSearchResultScroller").get_by_text(search_text, exact=False),
        scope.locator(".slds-global-header__search-scope").get_by_text(search_text, exact=False),
    ]


class UserDetailPage(BasePage):
    """Opens Manage Users setup page and clicks Login / Login As."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._tried_classic_url = False
        self._tried_global_search = False

    async def open(
        self,
        user_id: str,
        *,
        instance_url: str | None = None,
        user_name: str | None = None,
        username: str | None = None,
        timeout_ms: int = 45_000,
    ) -> None:
        if not user_id:
            raise UserDetailPageError("Missing user_id for impersonation navigation")

        url = build_manage_users_url(instance_url or "", user_id)
        logger.info("user_detail.navigate user_id=%s url=%s", user_id, url)
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception as exc:
            await self.screenshot("user_detail_goto_failed")
            raise UserDetailPageError(f"Failed to open user record {user_id}: {exc}") from exc

        try:
            await self.wait_for_lightning_ready(timeout=min(timeout_ms, 30_000))
        except Exception:
            pass

        await self._ensure_login_surface(
            user_id=user_id,
            instance_url=instance_url or "",
            user_name=user_name,
            username=username,
            timeout_ms=timeout_ms,
        )

    async def _ensure_login_surface(
        self,
        *,
        user_id: str,
        instance_url: str,
        user_name: str | None,
        username: str | None,
        timeout_ms: int,
    ) -> None:
        """Reach a page (or iframe) that exposes the Login / Login As control."""
        elapsed = 0
        poll = 500
        search_terms = pick_global_search_terms(user_name, username)

        while elapsed < timeout_ms:
            self._check_cancelled()

            found = await self._find_login_button(per_locator_ms=800)
            if found:
                logger.info("user_detail.login_surface_ready url=%s", (self.page.url or "")[:120])
                return

            current_url = self.page.url or ""
            if is_lightning_user_record_url(current_url):
                logger.info(
                    "user_detail.lightning_record_view — opening User Detail setup page"
                )
                if await self._click_user_detail():
                    await self.cancellable_sleep(2500)
                    elapsed += poll
                    continue

            if search_terms and not self._tried_global_search:
                self._tried_global_search = True
                for term in search_terms:
                    logger.info("user_detail.global_search term=%s", term[:80])
                    if await self._navigate_via_global_search(
                        term,
                        user_id=user_id,
                        instance_url=instance_url,
                    ):
                        await self.cancellable_sleep(2000)
                        break
                elapsed += poll
                continue

            if instance_url and not self._tried_classic_url:
                self._tried_classic_url = True
                classic_url = build_classic_user_detail_url(instance_url, user_id)
                logger.info("user_detail.fallback_classic url=%s", classic_url)
                try:
                    await self.page.goto(
                        classic_url,
                        wait_until="domcontentloaded",
                        timeout=timeout_ms,
                    )
                    await self.cancellable_sleep(2000)
                except Exception as exc:
                    logger.warning("user_detail.classic_goto_failed %s", exc)
                elapsed += poll
                continue

            await self.cancellable_sleep(poll)
            elapsed += poll

        await self.screenshot("user_detail_not_loaded")
        raise UserDetailPageError(
            f"User detail page did not expose Login for user_id={user_id} within {timeout_ms}ms. "
            "Open User Detail from the Lightning User record, or search the user in global search."
        )

    async def _navigate_via_global_search(
        self,
        search_text: str,
        *,
        user_id: str,
        instance_url: str,
    ) -> bool:
        """Use header global search to open the User record, then User Detail."""
        base = lightning_base_url(instance_url)
        if base and not is_lightning_user_record_url(self.page.url or ""):
            try:
                await self.page.goto(
                    f"{base}/lightning/page/home",
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )
                await self.wait_for_lightning_ready(timeout=20_000)
            except Exception as exc:
                logger.warning("user_detail.global_search_home_failed %s", exc)

        found_input = await find_visible_in_scopes(
            all_scopes(self.page),
            _global_search_input_locators,
            per_locator_ms=800,
        )
        if not found_input:
            logger.warning("user_detail.global_search_input_missing")
            return False

        _scope, search_input = found_input
        try:
            await search_input.first.click(timeout=3000)
            await search_input.first.fill(search_text, timeout=5000)
            await self.cancellable_sleep(1200)
            await self.page.keyboard.press("Enter")
            await self.cancellable_sleep(1500)
        except Exception as exc:
            logger.warning("user_detail.global_search_fill_failed %s", exc)
            return False

        if await self._click_search_user_result(search_text, user_id):
            await self._wait_for_user_record(user_id, timeout_ms=15_000)
            if is_lightning_user_record_url(self.page.url or ""):
                await self._click_user_detail()
            return True

        if is_lightning_user_record_url(self.page.url or ""):
            await self._click_user_detail()
            return True

        return False

    async def _click_search_user_result(self, search_text: str, user_id: str) -> bool:
        found = await find_visible_in_scopes(
            all_scopes(self.page),
            lambda scope: _global_search_result_locators(scope, search_text, user_id),
            per_locator_ms=1000,
        )
        if not found:
            return False
        _scope, locator = found
        try:
            await locator.first.scroll_into_view_if_needed(timeout=2000)
            await locator.first.click(timeout=5000)
            logger.info("user_detail.global_search_result_clicked")
            return True
        except Exception as exc:
            logger.warning("user_detail.global_search_result_click_failed %s", exc)
            return False

    async def _wait_for_user_record(self, user_id: str, *, timeout_ms: int) -> None:
        uid_short = user_id[:15]
        elapsed = 0
        poll = 400
        while elapsed < timeout_ms:
            url = self.page.url or ""
            if user_id in url or uid_short in url:
                return
            if is_lightning_user_record_url(url):
                return
            await self.cancellable_sleep(poll)
            elapsed += poll

    async def _find_login_button(
        self, *, per_locator_ms: int = 500
    ) -> tuple[PageOrFrame, Locator] | None:
        return await find_visible_in_scopes(
            all_scopes(self.page),
            _login_button_locators,
            per_locator_ms=per_locator_ms,
        )

    async def _click_user_detail(self) -> bool:
        found = await find_visible_in_scopes(
            all_scopes(self.page),
            _user_detail_locators,
            per_locator_ms=800,
        )
        if not found:
            return False
        _scope, locator = found
        try:
            await locator.first.scroll_into_view_if_needed(timeout=2000)
            await locator.first.click(timeout=5000)
            logger.info("user_detail.click_user_detail success")
            return True
        except Exception as exc:
            logger.warning("user_detail.click_user_detail_failed %s", exc)
            return False

    async def click_login(self, *, timeout_ms: int = 30_000) -> None:
        """Click Login or Login As on the User detail page (main page or setup iframe)."""
        elapsed = 0
        poll = 500
        last_error: Exception | None = None
        while elapsed < timeout_ms:
            self._check_cancelled()

            if is_lightning_user_record_url(self.page.url or ""):
                await self._click_user_detail()
                await self.cancellable_sleep(1500)

            found = await self._find_login_button(per_locator_ms=800)
            if found:
                _scope, locator = found
                try:
                    await locator.first.scroll_into_view_if_needed(timeout=2000)
                    await locator.first.click(timeout=5000)
                    logger.info("user_detail.click_login success")
                    return
                except Exception as exc:
                    last_error = exc

            await self.cancellable_sleep(poll)
            elapsed += poll

        await self.screenshot("user_login_button_missing")
        raise UserDetailPageError(
            "Could not find the 'Login' or 'Login As' button on the User detail page"
        ) from last_error
