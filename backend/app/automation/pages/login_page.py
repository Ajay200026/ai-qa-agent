import logging

from app.automation.pages.base_page import BasePage

logger = logging.getLogger(__name__)


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

        await self.wait_for_lightning_ready(timeout=90000)
        logger.info("Logged in as %s — URL: %s", username, self.page.url)

    async def login_with_oauth(self, instance_url: str, access_token: str) -> None:
        frontdoor_url = f"{instance_url.rstrip('/')}/secur/frontdoor.jsp?sid={access_token}"
        await self.page.goto(frontdoor_url, wait_until="domcontentloaded", timeout=60000)
        await self.wait_for_lightning_ready(timeout=90000)
        logger.info("OAuth session injected via frontdoor.jsp")

    async def is_logged_in(self) -> bool:
        try:
            await self.wait_for_lightning_ready(timeout=15000)
            return True
        except Exception:
            return False
