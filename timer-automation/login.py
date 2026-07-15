from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from playwright.async_api import Error as PlaywrightError, Page, TimeoutError as PlaywrightTimeoutError

from browser import BrowserFactory, capture_screenshot, goto_and_wait, is_session_authenticated, save_page_html
from config import Settings, TIMEZONE


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoginResult:
    success: bool
    started_at: datetime
    completed_at: datetime | None = None
    timer_url: str | None = None
    screenshot_path: str | None = None
    html_path: str | None = None
    error: str | None = None


class LoginService:
    def __init__(self, settings: Settings, browser_factory: BrowserFactory | None = None) -> None:
        self.settings = settings
        self.browser_factory = browser_factory or BrowserFactory(settings)

    async def login_and_open_timer(self, keep_open: bool = False) -> LoginResult:
        started_at = datetime.now(TIMEZONE)
        page: Page | None = None
        try:
            async with self.browser_factory.session(use_storage_state=False) as session:
                page = session.page
                try:
                    await perform_login(page, self.settings)
                    await session.context.storage_state(path=str(self.settings.storage_state_path))
                    logger.info("Persisted storage state to %s", self.settings.storage_state_path)
                    await goto_and_wait(page, self.settings.timer_url, self.settings.login_timeout)
                    logger.info("Timer page loaded; no timer controls will be touched")

                    if keep_open:
                        await monitor_timer_page_until_logout(page, self.settings)

                    return LoginResult(
                        success=True,
                        started_at=started_at,
                        completed_at=datetime.now(TIMEZONE),
                        timer_url=page.url,
                    )
                except Exception as exc:
                    logger.exception("Login flow failed; current URL: %s", page.url)
                    screenshot_path = await capture_screenshot(page, self.settings.screenshot_dir, "login_failure")
                    html_path = await save_page_html(page, self.settings.log_dir, "login_failure")
                    return LoginResult(
                        success=False,
                        started_at=started_at,
                        completed_at=datetime.now(TIMEZONE),
                        screenshot_path=screenshot_path,
                        html_path=html_path,
                        error=f"{type(exc).__name__}: {exc}",
                    )
        except Exception as exc:
            logger.exception("Login flow failed before page diagnostics were available")
            return LoginResult(
                success=False,
                started_at=started_at,
                completed_at=datetime.now(TIMEZONE),
                error=f"{type(exc).__name__}: {exc}",
            )


async def perform_login(page: Page, settings: Settings) -> None:
    await goto_and_wait(page, settings.login_url, settings.login_timeout)
    logger.info("Attempting login for %s at %s", settings.login_email, page.url)

    email = page.locator(
        "input[type='email'], input[name='email'], input[name='username'], "
        "input[autocomplete='username'], input[id*='email' i], input[name*='email' i], "
        "input[placeholder*='email' i], input[aria-label*='email' i], "
        "input[placeholder*='username' i], input[aria-label*='username' i]"
    ).first
    password = page.locator(
        "input[type='password'], input[name='password'], input[autocomplete='current-password'], "
        "input[id*='password' i], input[name*='password' i], input[placeholder*='password' i], "
        "input[aria-label*='password' i]"
    ).first
    submit = page.locator(
        "button[type='submit'], input[type='submit'], button:has-text('Log in'), "
        "button:has-text('Login'), button:has-text('Sign in'), button:has-text('Sign In'), "
        "[role='button']:has-text('Log in'), [role='button']:has-text('Login'), "
        "[role='button']:has-text('Sign in')"
    ).first

    await email.wait_for(state="visible", timeout=settings.login_timeout)
    await email.fill(settings.login_email)
    await password.fill(settings.login_password)
    await submit.click()

    await confirm_authenticated(page, settings)


async def confirm_authenticated(page: Page, settings: Settings) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=settings.login_timeout)
    except PlaywrightTimeoutError:
        logger.warning("Timed out waiting for networkidle after login; checking auth state")

    try:
        await page.wait_for_url(lambda url: "/login" not in url.lower(), timeout=settings.login_timeout)
    except PlaywrightTimeoutError:
        pass

    if not await is_session_authenticated(page):
        raise RuntimeError(f"Login did not reach an authenticated state; current URL: {page.url}")

    logger.info("Login succeeded; authenticated URL: %s", page.url)


async def monitor_timer_page_until_logout(page: Page, settings: Settings, interval_seconds: int = 90) -> None:
    import asyncio

    logout_hour, logout_minute = [int(part) for part in settings.logout_time.split(":", maxsplit=1)]
    logger.info("Monitoring timer page until %s %s", settings.logout_time, TIMEZONE.key)

    while True:
        now = datetime.now(TIMEZONE)
        if (now.hour, now.minute) >= (logout_hour, logout_minute):
            logger.info("Reached scheduled logout time; ending timer page monitor")
            return

        try:
            if page.is_closed():
                logger.warning("Timer page was closed")
                return
            await page.title()
            if not await is_session_authenticated(page):
                logger.warning("Session appears expired; will not re-authenticate or touch timer controls")
            else:
                logger.info("Timer page session check OK")
        except PlaywrightError:
            logger.exception("Timer page check failed")
            return

        await asyncio.sleep(interval_seconds)
