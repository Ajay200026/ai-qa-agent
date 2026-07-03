import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from uuid import UUID

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from app.automation.playwright_paths import ensure_playwright_browsers_path
from app.core.config import get_settings
from app.services.execution_registry import execution_registry

logger = logging.getLogger(__name__)


class BrowserManager:
    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self.settings = get_settings()

    def _configure_browsers_path(self) -> None:
        resolved = ensure_playwright_browsers_path(self.settings.playwright_browsers_path)
        if not resolved:
            raise RuntimeError(
                "Playwright Chromium is not installed. Run: playwright install chromium"
            )

    async def start(self) -> None:
        if self._browser is None:
            self._configure_browsers_path()
            self._playwright = await async_playwright().start()
            width = self.settings.playwright_viewport_width
            height = self.settings.playwright_viewport_height
            launch_args: list[str] = []
            if not self.settings.playwright_headless:
                launch_args.extend([
                    f"--window-size={width},{height}",
                    "--window-position=0,0",
                ])

            self._browser = await self._playwright.chromium.launch(
                headless=self.settings.playwright_headless,
                args=launch_args,
            )
            logger.info(
                "Playwright browser started (viewport %dx%d, headless=%s)",
                width,
                height,
                self.settings.playwright_headless,
            )

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Playwright browser stopped")

    @asynccontextmanager
    async def new_context(
        self,
        execution_id: UUID,
        *,
        record_video: bool = False,
    ) -> AsyncGenerator[tuple[BrowserContext, Page], None]:
        if not self._browser:
            await self.start()

        artifacts_dir = self.settings.artifacts_dir / str(execution_id)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        width = self.settings.playwright_viewport_width
        height = self.settings.playwright_viewport_height

        context_options: dict = {
            "viewport": {"width": width, "height": height},
            "screen": {"width": width, "height": height},
            "device_scale_factor": 1,
            "ignore_https_errors": True,
        }
        if record_video:
            context_options["record_video_dir"] = str(artifacts_dir / "video")

        assert self._browser is not None
        context = await self._browser.new_context(**context_options)
        context.set_default_timeout(min(self.settings.playwright_timeout_ms, 10_000))
        page = await context.new_page()

        execution_registry.register_context(execution_id, context)
        try:
            yield context, page
        finally:
            execution_registry.unregister_context(execution_id)
            await context.close()


browser_manager = BrowserManager()
