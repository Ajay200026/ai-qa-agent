import logging
import re

from app.automation.pages.base_page import BasePage
from app.automation.pages.customer_lifecycle_page import QUEUES_TAB_NAMES

logger = logging.getLogger(__name__)


class OnboardingPage(BasePage):
    async def open_customer_lifecycle(self) -> None:
        from app.automation.pages.customer_lifecycle_page import CustomerLifecyclePage

        queues = CustomerLifecyclePage(self.page, self.artifacts_dir, self.execution_id)
        if await queues.is_on_queues_page():
            logger.info("Already on Customer Life Cycle Queues — skipping tab navigation")
            return

        for name in QUEUES_TAB_NAMES:
            try:
                tab = self.page.get_by_role("tab", name=name)
                await self.click_locator(tab, timeout=8_000)
                await self.cancellable_sleep(1500)
                logger.info("Opened tab: %s", name)
                return
            except Exception:
                continue

        try:
            tab = self.page.get_by_role("tab", name=re.compile(r"Customer.*Life.*Cycle", re.I))
            await self.click_locator(tab, timeout=8_000)
            await self.cancellable_sleep(1500)
            logger.info("Opened Customer Life Cycle tab via pattern match")
        except Exception:
            await queues.wait_for_queues_ready()
            logger.info("Queues page detected after tab navigation fallback")
