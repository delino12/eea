from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from browser import BrowserFactory, capture_screenshot, goto_and_wait, is_login_url
from config import Settings, TIMEZONE


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LogoutResult:
    success: bool
    started_at: datetime
    completed_at: datetime | None = None
    attempts: int = 0
    screenshot_path: str | None = None
    error: str | None = None


class LogoutService:
    def __init__(self, settings: Settings, browser_factory: BrowserFactory | None = None) -> None:
        self.settings = settings
        self.browser_factory = browser_factory or BrowserFactory(settings)

    async def logout(self) -> LogoutResult:
        started_at = datetime.now(TIMEZONE)
        page: Page | None = None
        last_error: Exception | None = None
        attempts = 0

        try:
            async with self.browser_factory.session(use_storage_state=True) as session:
                page = session.page
                await goto_and_wait(page, self.settings.timer_url, self.settings.login_timeout)

                for attempts in range(1, 4):
                    try:
                        logger.info("Logout attempt %s", attempts)
                        await perform_logout(page, self.settings)
                        return LogoutResult(
                            success=True,
                            started_at=started_at,
                            completed_at=datetime.now(TIMEZONE),
                            attempts=attempts,
                        )
                    except Exception as exc:
                        last_error = exc
                        logger.exception("Logout attempt %s failed", attempts)

                screenshot_path = await capture_screenshot(page, self.settings.screenshot_dir, "logout_failure")
                return LogoutResult(
                    success=False,
                    started_at=started_at,
                    completed_at=datetime.now(TIMEZONE),
                    attempts=attempts,
                    screenshot_path=screenshot_path,
                    error=f"{type(last_error).__name__}: {last_error}",
                )
        except Exception as exc:
            logger.exception("Logout flow failed")
            screenshot_path = await capture_screenshot(page, self.settings.screenshot_dir, "logout_failure")
            return LogoutResult(
                success=False,
                started_at=started_at,
                completed_at=datetime.now(TIMEZONE),
                attempts=attempts,
                screenshot_path=screenshot_path,
                error=f"{type(exc).__name__}: {exc}",
            )


async def perform_logout(page: Page, settings: Settings) -> None:
    menu_selectors = (
        "[data-testid='user-menu']",
        "[data-test='user-menu']",
        "button[aria-label*='profile' i]",
        "button[aria-label*='account' i]",
        "img[alt*='avatar' i]",
    )
    logout_selectors = (
        "[data-testid='logout']",
        "[data-test='logout']",
        "button:has-text('Logout')",
        "a:has-text('Logout')",
        "text=/log out/i",
    )

    opened_menu = False
    for selector in menu_selectors:
        try:
            target = page.locator(selector).first
            if await target.is_visible(timeout=2000):
                await target.click()
                opened_menu = True
                break
        except Exception:
            continue

    if not opened_menu:
        logger.warning("Profile menu selector not found; trying visible logout action directly")

    clicked_logout = False
    for selector in logout_selectors:
        try:
            target = page.locator(selector).first
            if await target.is_visible(timeout=3000):
                await target.click()
                clicked_logout = True
                break
        except Exception:
            continue

    if not clicked_logout:
        raise RuntimeError("Could not find logout control")

    try:
        await page.wait_for_url(lambda url: "/login" in url.lower(), timeout=settings.login_timeout)
    except PlaywrightTimeoutError as exc:
        if not await is_login_url(page):
            raise RuntimeError(f"Logout did not redirect to login page; current URL: {page.url}") from exc

    logger.info("Logout succeeded; current URL: %s", page.url)
