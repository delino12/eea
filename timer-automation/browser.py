from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from config import Settings, TIMEZONE


logger = logging.getLogger(__name__)


class BrowserSession:
    def __init__(
        self,
        playwright: Playwright,
        browser: Browser,
        context: BrowserContext,
        page: Page,
    ) -> None:
        self.playwright = playwright
        self.browser = browser
        self.context = context
        self.page = page


class BrowserFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @asynccontextmanager
    async def session(self, use_storage_state: bool = True) -> AsyncIterator[BrowserSession]:
        playwright = await async_playwright().start()
        browser: Browser | None = None
        context: BrowserContext | None = None
        try:
            logger.info("Launching Chromium, headless=%s", self.settings.headless)
            browser = await playwright.chromium.launch(headless=self.settings.headless)
            context_options: dict[str, Any] = {
                "base_url": self.settings.app_url,
                "viewport": {"width": 1440, "height": 1000},
            }
            if use_storage_state and self.settings.storage_state_path.exists():
                context_options["storage_state"] = str(self.settings.storage_state_path)

            context = await browser.new_context(**context_options)
            context.set_default_timeout(self.settings.login_timeout)
            page = await context.new_page()
            yield BrowserSession(playwright, browser, context, page)
        finally:
            if context is not None:
                try:
                    await context.close()
                    logger.info("Browser context closed")
                except Exception:
                    logger.exception("Failed to close browser context")
            if browser is not None:
                try:
                    await browser.close()
                    logger.info("Browser closed")
                except Exception:
                    logger.exception("Failed to close browser")
            await playwright.stop()


async def capture_screenshot(page: Page | None, directory: Path, prefix: str) -> str | None:
    if page is None:
        return None
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(TIMEZONE).strftime("%Y%m%d_%H%M%S")
    path = directory / f"{prefix}_{timestamp}.png"
    try:
        await page.screenshot(path=str(path), full_page=True)
        logger.info("Saved screenshot to %s", path)
        return str(path)
    except Exception:
        logger.exception("Failed to capture screenshot")
        return None


async def goto_and_wait(page: Page, url: str, timeout: int) -> None:
    logger.info("Navigating to %s", url)
    await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    await page.wait_for_load_state("networkidle", timeout=timeout)


async def is_login_url(page: Page) -> bool:
    url = page.url.lower()
    return "/login" in url or "/sign-in" in url or "/signin" in url


async def is_session_authenticated(page: Page) -> bool:
    if await is_login_url(page):
        return False
    selectors = (
        "[data-testid='user-menu']",
        "[data-test='user-menu']",
        "button:has-text('Logout')",
        "text=/dashboard/i",
        "text=/timer/i",
    )
    for selector in selectors:
        try:
            if await page.locator(selector).first.is_visible(timeout=1500):
                return True
        except Exception:
            continue
    return not await is_login_url(page)
