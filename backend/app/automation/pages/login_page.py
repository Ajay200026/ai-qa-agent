import logging
import re
from urllib.parse import quote

from app.automation.pages.base_page import BasePage

logger = logging.getLogger(__name__)

_LIGHTNING_URL = re.compile(r"lightning\.force\.com|\.salesforce\.com", re.IGNORECASE)
_LOGIN_HOST = re.compile(r"(login|test)\.salesforce\.com", re.IGNORECASE)


class LoginPage(BasePage):
    async def _fill_field(self, locator_name: str, value: str, fallbacks: list[str]) -> None:
        try:
            await self.safe_fill(locator_name, value)
            return
        except RuntimeError:
            pass
        for selector in fallbacks:
            try:
                field = self.page.locator(selector).first
                await field.wait_for(state="visible", timeout=8000)
                await field.fill(value)
                return
            except Exception as exc:
                logger.debug("Fallback fill %s failed: %s", selector, exc)
        raise RuntimeError(f"Could not fill {locator_name}")

    async def _click_login(self) -> None:
        candidates = [
            ("login.submit", None),
            ("login.submit_prod", None),
        ]
        for locator_name, _ in candidates:
            try:
                await self.safe_click(locator_name)
                return
            except RuntimeError:
                continue
        for selector in ['input[type="submit"]', 'button[type="submit"]', "#Login"]:
            try:
                btn = self.page.locator(selector).first
                await btn.wait_for(state="visible", timeout=5000)
                await btn.click()
                return
            except Exception:
                continue
        raise RuntimeError("Could not find Salesforce login button")

    async def _detect_login_blocker(self) -> str | None:
        url = self.page.url.lower()
        if "verification" in url or "emc=" in url:
            return "Salesforce requires email/SMS verification — complete MFA manually or use OAuth session."
        if await self.page.locator("text=Verify your identity").count() > 0:
            return "Salesforce MFA verification page detected."
        if await self.page.locator("text=Check Your Email").count() > 0:
            return "Salesforce sent a verification email — cannot automate this step."
        return None

    async def login_with_credentials(self, login_url: str, username: str, password: str) -> None:
        await self.page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
        await self.page.wait_for_timeout(1500)

        await self._fill_field(
            "login.username",
            username,
            ["#username", 'input[name="username"]', 'input[type="email"]'],
        )
        await self._fill_field(
            "login.password",
            password,
            ["#password", 'input[name="password"]', 'input[type="password"]'],
        )
        await self._click_login()

        blocker = await self._detect_login_blocker()
        if blocker:
            await self.screenshot("login_blocker")
            raise RuntimeError(blocker)

        await self.wait_for_lightning_ready(timeout=45_000)
        logger.info("Logged in as %s — URL: %s", username, self.page.url)

    async def login_with_oauth(self, instance_url: str, access_token: str) -> None:
        base = instance_url.rstrip("/")
        frontdoor_url = (
            f"{base}/secur/frontdoor.jsp"
            f"?sid={quote(access_token, safe='')}"
            f"&retURL={quote('/lightning/page/home')}"
        )
        await self.page.goto(frontdoor_url, wait_until="domcontentloaded", timeout=60_000)
        await self.page.wait_for_timeout(800)

        on_login_form = (
            await self.page.locator("#username").count() > 0
            or await self.page.locator('input[name="username"]').count() > 0
        )
        login_required = await self.page.locator("text=you have to log in").count() > 0
        if on_login_form or login_required:
            await self.screenshot("oauth_frontdoor_failed")
            raise RuntimeError(
                "OAuth session could not open Salesforce in the browser. "
                "Re-authorize the org (Authorize via Web) to grant UI access, "
                "or use Username & Password on the Salesforce Orgs page."
            )

        blocker = await self._detect_login_blocker()
        if blocker:
            await self.screenshot("login_blocker")
            raise RuntimeError(blocker)

        await self.wait_for_lightning_ready(timeout=30_000)
        logger.info("OAuth session injected via frontdoor.jsp — URL: %s", self.page.url)

    async def is_logged_in(self) -> bool:
        url = self.page.url or ""
        if not url or url == "about:blank":
            return False
        if _LOGIN_HOST.search(url) and "secur/frontdoor" not in url.lower():
            try:
                if await self.page.locator("#username, input[name='username']").first.is_visible(
                    timeout=1500
                ):
                    return False
            except Exception:
                pass
        if not _LIGHTNING_URL.search(url):
            return False
        try:
            await self.wait_for_lightning_ready(timeout=8000)
            return True
        except Exception:
            return "/lightning/" in url.lower()
