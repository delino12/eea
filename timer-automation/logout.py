from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from browser import BrowserFactory, capture_screenshot, goto_and_wait, is_login_url
from config import Settings, TIMEZONE
from timer import stop_timer_if_running


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
                        await stop_timer_if_running(page, self.settings)
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
    direct_logout_selectors = (
        "[data-testid='sign-out']",
        "[data-test='sign-out']",
        "[data-testid='logout']",
        "[data-test='logout']",
        "a:has-text('Sign out')",
        "button:has-text('Sign out')",
        "[role='menuitem']:has-text('Sign out')",
        "[role='button']:has-text('Sign out')",
        "text=/sign\\s*out/i",
        "a:has-text('Logout')",
        "button:has-text('Logout')",
        "[role='menuitem']:has-text('Logout')",
        "[role='button']:has-text('Logout')",
        "text=/log\\s*out/i",
    )
    menu_selectors = (
        "[data-testid='user-menu']",
        "[data-test='user-menu']",
        "button[aria-label*='profile' i]",
        "button[aria-label*='account' i]",
        "img[alt*='avatar' i]",
    )
    if await click_logout_action(page, direct_logout_selectors, "direct/sidebar"):
        await confirm_logged_out(page, settings)
        return

    opened_menu = False
    for selector in menu_selectors:
        try:
            target = page.locator(selector).first
            if await target.is_visible(timeout=2000):
                await target.scroll_into_view_if_needed(timeout=settings.login_timeout)
                await target.click()
                opened_menu = True
                break
        except Exception:
            continue

    if not opened_menu:
        logger.warning("Profile menu selector not found; trying visible logout action directly")

    if not await click_logout_action(page, direct_logout_selectors, "profile/direct fallback"):
        raise RuntimeError("Could not find logout control")

    await confirm_logged_out(page, settings)


async def click_logout_action(page: Page, selectors: tuple[str, ...], source: str) -> bool:
    for selector in selectors:
        try:
            target = page.locator(selector).first
            if await target.is_visible(timeout=3000):
                logger.info("Clicking %s sign-out control using selector %s", source, selector)
                await target.scroll_into_view_if_needed(timeout=5000)
                await target.click(timeout=5000)
                return True
        except Exception as exc:
            logger.debug("Logout selector %s did not work: %s", selector, exc)
            continue

    return await click_logout_with_dom(page, source)


async def click_logout_with_dom(page: Page, source: str) -> bool:
    try:
        clicked = await page.evaluate(
            """
            () => {
                const isVisible = (el) => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.visibility !== 'hidden'
                        && style.display !== 'none'
                        && rect.width > 0
                        && rect.height > 0;
                };
                const candidates = Array.from(
                    document.querySelectorAll('a, button, [role="button"], [role="menuitem"], div, span')
                );
                const target = candidates.find((el) => /(sign\\s*out|log\\s*out|logout)/i.test(el.textContent || '')
                    && isVisible(el));
                if (!target) {
                    return false;
                }
                const clickable = target.closest('a, button, [role="button"], [role="menuitem"]') || target;
                clickable.click();
                return true;
            }
            """
        )
        if clicked:
            logger.info("Clicking %s sign-out control using DOM text fallback", source)
            return True
    except Exception as exc:
        logger.debug("DOM sign-out fallback failed: %s", exc)
    return False


async def confirm_logged_out(page: Page, settings: Settings) -> None:
    try:
        await page.wait_for_url(lambda url: "/login" in url.lower(), timeout=settings.login_timeout)
    except PlaywrightTimeoutError as exc:
        if not await is_login_url(page):
            raise RuntimeError(f"Logout did not redirect to login page; current URL: {page.url}") from exc

    logger.info("Logout succeeded; current URL: %s", page.url)
