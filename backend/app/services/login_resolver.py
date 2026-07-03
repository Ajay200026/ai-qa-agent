"""LoginResolver: Login As another user via Salesforce REST SOQL + UI impersonation.

Flow:
1. Admin logs into Salesforce in the browser (Playwright).
2. SOQL User lookup via REST API (SOAP login + /query) — fast, no Inspector UI.
3. Open User record in a new tab (Manage Users setup URL).
4. Click Login / Login As.
5. Wait for impersonated session and capture screenshot.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from playwright.async_api import Page

from app.automation.pages.base_page import BasePage
from app.automation.pages.user_detail_page import (
    UserDetailPage,
    UserDetailPageError,
    is_lightning_user_record_url,
)
from app.automation.self_healing import retry_with_heal
from app.models.salesforce_org import SalesforceOrg
from app.schemas.login_as import ImpersonationResult, ResolvedUser
from app.services.salesforce_query import (
    SoqlAuthError,
    SoqlClient,
    SoqlExecutionError,
    SoqlValidationError,
)

logger = logging.getLogger(__name__)

_LOGGED_IN_AS = re.compile(r"logged\s+in\s+as", re.IGNORECASE)


class LoginResolverError(RuntimeError):
    """Base class for LoginResolver failures."""


class LoginResolverNoUserError(LoginResolverError):
    """Raised when the SOQL lookup returns zero rows."""


class LoginResolverNavigationError(LoginResolverError):
    """Raised when the User detail page cannot be opened."""


class LoginResolverButtonError(LoginResolverError):
    """Raised when the Login button cannot be located or clicked."""


def _safe(value: str | None) -> str:
    return (value or "").strip()


def _escape_soql_literal(value: str) -> str:
    cleaned = re.sub(r"[\x00-\x1f]", "", value or "")
    return cleaned.replace("\\", "\\\\").replace("'", "\\'")


def build_user_lookup_soql(bottler_id: str, onboarding_role: str) -> str:
    bottler = _escape_soql_literal(_safe(bottler_id))
    role = _escape_soql_literal(_safe(onboarding_role))
    return (
        "SELECT Id, Name, Username, cfs_ob__Bottler__c, cfs_ob__Onboarding_Role__c "
        "FROM User "
        "WHERE IsActive = true "
        f"AND cfs_ob__Bottler__c = '{bottler}' "
        f"AND cfs_ob__Onboarding_Role__c = '{role}' "
        "LIMIT 1"
    )


@dataclass
class _ResolverCache:
    users: dict[str, ResolvedUser] = field(default_factory=dict)
    current_identity_key: str | None = None

    @staticmethod
    def key(bottler_id: str, onboarding_role: str) -> str:
        return f"{_safe(bottler_id).lower()}|{_safe(onboarding_role).lower()}"


_EXECUTION_CACHES: dict[str, _ResolverCache] = {}


def reset_execution_cache(execution_id: object) -> None:
    _EXECUTION_CACHES.pop(str(execution_id), None)


class LoginResolver:
    """REST SOQL user lookup + browser impersonation."""

    def __init__(
        self,
        page: Page,
        org: SalesforceOrg,
        credentials: dict[str, Any],
        artifacts_dir: Path | None = None,
        execution_id: UUID | None = None,
        *,
        max_attempts: int = 3,
    ) -> None:
        self.page = page
        self.org = org
        self.credentials = credentials or {}
        self.artifacts_dir = artifacts_dir
        self.execution_id = execution_id
        self.max_attempts = max_attempts
        self._impersonation_tab: Page | None = None
        self._user_page = UserDetailPage(page, artifacts_dir, execution_id)
        self._base = BasePage(page, artifacts_dir, execution_id)
        cache_key = str(execution_id) if execution_id is not None else id(self)
        self._cache_key = str(cache_key)
        self._cache = _EXECUTION_CACHES.setdefault(self._cache_key, _ResolverCache())

    @property
    def current_identity_key(self) -> str | None:
        return self._cache.current_identity_key

    def sync_page(self, page: Page) -> None:
        self.page = page
        self._user_page.page = page
        self._base.page = page

    async def login_as(
        self,
        bottler_id: str,
        onboarding_role: str,
        *,
        force: bool = False,
    ) -> ImpersonationResult:
        bottler = _safe(bottler_id)
        role = _safe(onboarding_role)
        if not bottler or not role:
            raise LoginResolverError(
                "login_as requires non-empty bottler_id and onboarding_role"
            )

        identity_key = _ResolverCache.key(bottler, role)
        if not force and self._cache.current_identity_key == identity_key:
            cached = self._cache.users.get(identity_key)
            if cached and await self._verify_impersonation_active(cached):
                logger.info(
                    "login_resolver.skip already_impersonated bottler=%s role=%s",
                    bottler,
                    role,
                )
                return ImpersonationResult(success=True, **cached.model_dump())
            if cached:
                logger.info(
                    "login_resolver.cache_stale re-impersonating bottler=%s role=%s",
                    bottler,
                    role,
                )

        resolved = await self._resolve_user(bottler, role)

        async def _heal() -> None:
            tab = self._impersonation_tab or self.page
            try:
                await BasePage(tab, self.artifacts_dir, self.execution_id).wait_for_lightning_ready(
                    timeout=10_000
                )
            except Exception:
                pass

        await retry_with_heal(
            lambda: self._open_user_record(resolved),
            heal_fn=_heal,
            max_attempts=self.max_attempts,
        )
        await retry_with_heal(
            self._click_login_button,
            heal_fn=_heal,
            max_attempts=self.max_attempts,
        )
        await retry_with_heal(
            lambda: self._wait_for_impersonation_ready(resolved),
            heal_fn=_heal,
            max_attempts=self.max_attempts,
        )

        self._cache.users[identity_key] = resolved
        self._cache.current_identity_key = identity_key

        logger.info(
            "login_resolver.ready user_id=%s bottler=%s role=%s",
            resolved.user_id,
            bottler,
            role,
        )
        return ImpersonationResult(success=True, **resolved.model_dump())

    async def _resolve_user(
        self, bottler_id: str, onboarding_role: str
    ) -> ResolvedUser:
        logger.info(
            "login_resolver.resolve bottler=%s role=%s", bottler_id, onboarding_role
        )
        soql = build_user_lookup_soql(bottler_id, onboarding_role)
        client = SoqlClient(org=self.org, credentials=self.credentials, page=self.page)

        try:
            rows = await client.query_users(soql, limit=1)
        except SoqlAuthError as exc:
            raise LoginResolverError(
                "Salesforce API authentication failed for User SOQL lookup. "
                "The admin browser session could not be reused and SOAP login failed. "
                "Set the org instance URL, or add the security token to org credentials "
                "(password + token concatenated, or use the security_token field). "
                f"Detail: {exc}"
            ) from exc
        except SoqlValidationError as exc:
            raise LoginResolverError(f"Invalid User SOQL: {exc}") from exc
        except SoqlExecutionError as exc:
            raise LoginResolverError(
                f"User SOQL query failed (bottler={bottler_id}, role={onboarding_role}): {exc}"
            ) from exc

        if not rows or not rows[0].user_id:
            raise LoginResolverNoUserError(
                "No active Salesforce User found for "
                f"bottler='{bottler_id}', onboarding_role='{onboarding_role}'. "
                "Verify the Login As profile or the org's user metadata."
            )

        row = rows[0]
        return ResolvedUser(
            user_id=row.user_id,
            name=row.name,
            username=row.username,
            bottler=row.bottler or bottler_id,
            role=row.role or onboarding_role,
        )

    async def is_impersonating(self, bottler_id: str, onboarding_role: str) -> bool:
        key = _ResolverCache.key(bottler_id, onboarding_role)
        if self._cache.current_identity_key != key:
            return False
        cached = self._cache.users.get(key)
        if not cached:
            return False
        return await self._verify_impersonation_active(cached)

    async def _impersonation_banner_text(self, tab: Page | None = None) -> str:
        page = tab or self._impersonation_tab or self.page
        candidates = [
            page.get_by_text(_LOGGED_IN_AS),
            page.locator(".slds-global-header__item").filter(has_text=_LOGGED_IN_AS),
            page.locator("[class*='impersonat']"),
        ]
        for locator in candidates:
            try:
                el = locator.first
                if await el.is_visible(timeout=1500):
                    text = (await el.text_content() or "").strip()
                    if _LOGGED_IN_AS.search(text):
                        return text
                    parent = el.locator("xpath=ancestor::*[contains(@class,'header') or contains(@class,'banner')][1]")
                    if await parent.count() > 0:
                        parent_text = (await parent.first.text_content() or "").strip()
                        if _LOGGED_IN_AS.search(parent_text):
                            return parent_text
            except Exception:
                continue
        try:
            body = await page.locator("body").inner_text(timeout=3000)
            for line in body.splitlines():
                if _LOGGED_IN_AS.search(line):
                    return line.strip()
        except Exception:
            pass
        return ""

    async def _verify_impersonation_active(self, resolved: ResolvedUser) -> bool:
        tab = self._impersonation_tab or self.page
        banner = await self._impersonation_banner_text(tab)
        if not banner:
            return False
        lower = banner.lower()
        if resolved.name and resolved.name.lower() in lower:
            return True
        if resolved.username:
            username = resolved.username.lower()
            if username in lower:
                return True
            local = username.split("@")[0]
            if local and local in lower:
                return True
        return False

    async def _open_user_record(self, resolved: ResolvedUser) -> None:
        logger.info(
            "login_resolver.navigate user_id=%s name=%s (new tab)",
            resolved.user_id,
            (resolved.name or "")[:40],
        )
        self._impersonation_tab = await self.page.context.new_page()
        self._user_page = UserDetailPage(
            self._impersonation_tab, self.artifacts_dir, self.execution_id
        )
        try:
            await self._user_page.open(
                resolved.user_id,
                instance_url=self.org.instance_url,
                user_name=resolved.name,
                username=resolved.username,
            )
        except UserDetailPageError as exc:
            raise LoginResolverNavigationError(str(exc)) from exc

    async def _click_login_button(self) -> None:
        logger.info("login_resolver.click target=login_button")
        try:
            await self._user_page.click_login()
        except UserDetailPageError as exc:
            raise LoginResolverButtonError(str(exc)) from exc

    async def _wait_for_impersonation_ready(self, resolved: ResolvedUser) -> None:
        tab = self._impersonation_tab or self.page
        base = BasePage(tab, self.artifacts_dir, self.execution_id)
        await base.wait_for_lightning_ready(timeout=60_000)

        current_url = tab.url or ""
        if is_lightning_user_record_url(current_url) and "/view" in current_url.lower():
            raise LoginResolverButtonError(
                "Impersonation did not leave the Lightning User record page. "
                "Click User Detail → Login may be required, or the admin lacks Login As permission."
            )
        if "ManageUsers" in current_url and "address=" in current_url:
            raise LoginResolverButtonError(
                "Impersonation did not leave the User setup page"
            )

        if resolved.name:
            try:
                header = tab.locator(".slds-page-header__title, .profile-card-name").first
                if await header.is_visible(timeout=5000):
                    text = (await header.text_content() or "").strip()
                    if text and resolved.name.lower() not in text.lower():
                        logger.warning(
                            "login_resolver.name_mismatch expected=%s visible=%s",
                            resolved.name,
                            text[:80],
                        )
            except Exception:
                pass

        if not await self._verify_impersonation_active(resolved):
            await base.screenshot("login_as_impersonation_missing")
            raise LoginResolverButtonError(
                "Impersonation session not detected — expected a 'Logged in as' banner for "
                f"{resolved.name or resolved.user_id}. The browser is still the OAuth admin user."
            )

        await base.screenshot("login_as_impersonation_ready")
        self.sync_page(tab)
        logger.info("login_resolver.ready url=%s", current_url[:120])
