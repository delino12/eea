from __future__ import annotations

import argparse
import asyncio
from contextlib import suppress
import logging
from datetime import datetime
from types import TracebackType
from typing import Any

from browser import BrowserFactory, BrowserSession, capture_screenshot, goto_and_wait
from config import ConfigError, TIMEZONE, load_settings
from email_service import EmailService, RunReport
from logger import configure_logging
from login import LoginResult, LoginService, monitor_timer_page_until_logout, perform_login
from logout import LogoutResult, LogoutService, perform_logout
from scheduler import create_scheduler


logger = logging.getLogger(__name__)


def _runtime(started_at: datetime | None, completed_at: datetime | None) -> str | None:
    if not started_at or not completed_at:
        return None
    return str(completed_at - started_at).split(".")[0]


async def run_login() -> LoginResult:
    settings = load_settings()
    result = await LoginService(settings).login_and_open_timer(keep_open=True)
    EmailService(settings).send_report(
        RunReport(
            execution_date=datetime.now(TIMEZONE),
            login_time=result.started_at,
            logout_time=result.completed_at,
            total_runtime=_runtime(result.started_at, result.completed_at),
            success=result.success,
            status="Login session completed" if result.success else "Login failed",
            exception_details=result.error,
            screenshot_path=result.screenshot_path,
        )
    )
    return result


async def run_logout() -> LogoutResult:
    settings = load_settings()
    result = await LogoutService(settings).logout()
    EmailService(settings).send_report(
        RunReport(
            execution_date=datetime.now(TIMEZONE),
            login_time=None,
            logout_time=result.completed_at,
            total_runtime=_runtime(result.started_at, result.completed_at),
            success=result.success,
            status="Logout succeeded" if result.success else "Logout failed",
            exception_details=result.error,
            screenshot_path=result.screenshot_path,
        )
    )
    return result


class TimerAutomationRuntime:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.mailer = EmailService(self.settings)
        self.browser_factory = BrowserFactory(self.settings)
        self._session_cm: Any = None
        self._session: BrowserSession | None = None
        self._monitor_task: asyncio.Task[None] | None = None
        self._login_started_at: datetime | None = None

    async def login_job(self) -> None:
        if self._session is not None and not self._session.page.is_closed():
            logger.warning("Login job skipped because a browser session is already active")
            return

        self._login_started_at = datetime.now(TIMEZONE)
        page = None
        try:
            self._session_cm = self.browser_factory.session(use_storage_state=False)
            self._session = await self._session_cm.__aenter__()
            page = self._session.page
            await perform_login(page, self.settings)
            await self._session.context.storage_state(path=str(self.settings.storage_state_path))
            await goto_and_wait(page, self.settings.timer_url, self.settings.login_timeout)
            self._monitor_task = asyncio.create_task(
                monitor_timer_page_until_logout(page, self.settings, interval_seconds=90)
            )
            logger.info("Scheduler login finished; timer page is open for human operation")
        except Exception as exc:
            logger.exception("Scheduler login job failed")
            screenshot = await capture_screenshot(page, self.settings.screenshot_dir, "scheduler_login_failure")
            self.mailer.send_report(
                RunReport(
                    execution_date=datetime.now(TIMEZONE),
                    login_time=self._login_started_at,
                    logout_time=None,
                    total_runtime=None,
                    success=False,
                    status="Scheduler login failed",
                    exception_details=f"{type(exc).__name__}: {exc}",
                    screenshot_path=screenshot,
                )
            )
            await self.close_active_session(None, None, None)

    async def logout_job(self) -> None:
        started_at = self._login_started_at or datetime.now(TIMEZONE)
        completed_at: datetime | None = None
        screenshot: str | None = None
        error: str | None = None
        success = False

        try:
            if self._session is not None and not self._session.page.is_closed():
                await perform_logout(self._session.page, self.settings)
                success = True
            else:
                logger.warning("No active scheduler browser session; using stored session logout fallback")
                fallback = await LogoutService(self.settings).logout()
                success = fallback.success
                completed_at = fallback.completed_at
                screenshot = fallback.screenshot_path
                error = fallback.error
        except Exception as exc:
            logger.exception("Scheduler logout job failed")
            error = f"{type(exc).__name__}: {exc}"
            screenshot = await capture_screenshot(
                self._session.page if self._session is not None else None,
                self.settings.screenshot_dir,
                "scheduler_logout_failure",
            )
        finally:
            completed_at = completed_at or datetime.now(TIMEZONE)
            await self.close_active_session(None, None, None)

        self.mailer.send_report(
            RunReport(
                execution_date=datetime.now(TIMEZONE),
                login_time=started_at,
                logout_time=completed_at,
                total_runtime=_runtime(started_at, completed_at),
                success=success,
                status="Logout succeeded" if success else "Logout failed",
                exception_details=error,
                screenshot_path=screenshot,
            )
        )

    async def close_active_session(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._monitor_task
            self._monitor_task = None
        if self._session_cm is not None:
            await self._session_cm.__aexit__(exc_type, exc, traceback)
        self._session_cm = None
        self._session = None


async def run_scheduler() -> None:
    runtime = TimerAutomationRuntime()
    scheduler = create_scheduler(runtime.settings, runtime.login_job, runtime.logout_job)
    scheduler.start()
    logger.info("Scheduler started")
    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=False)
        await runtime.close_active_session(None, None, None)


async def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Timer automation login/logout scheduler")
    parser.add_argument("--action", choices=("login", "logout", "scheduler"), default="scheduler")
    args = parser.parse_args()

    try:
        if args.action == "login":
            result = await run_login()
            return 0 if result.success else 1
        if args.action == "logout":
            result = await run_logout()
            return 0 if result.success else 1
        await run_scheduler()
        return 0
    except ConfigError as exc:
        logger.error("Configuration error: %s", exc)
        return 2
    except KeyboardInterrupt:
        logger.info("Interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
