from __future__ import annotations

import logging
import sys
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import TIMEZONE, Settings


logger = logging.getLogger(__name__)


def create_scheduler(settings: Settings, login_job, logout_job) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        login_job,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=0, timezone=TIMEZONE),
        id="weekday_login",
        replace_existing=True,
        max_instances=1,
    )

    hour, minute = [int(part) for part in settings.logout_time.split(":", maxsplit=1)]
    scheduler.add_job(
        logout_job,
        CronTrigger(day_of_week="mon-fri", hour=hour, minute=minute, timezone=TIMEZONE),
        id="weekday_logout",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("Registered weekday scheduler jobs in %s", TIMEZONE.key)
    return scheduler


def cron_entries(project_dir: Path | None = None, python_executable: str | None = None) -> str:
    project = project_dir or Path(__file__).resolve().parent
    python = python_executable or sys.executable
    app_path = project / "app.py"
    return "\n".join(
        [
            f"0 9 * * 1-5  {python} {app_path} --action=login",
            f"0 18 * * 1-5 {python} {app_path} --action=logout",
        ]
    )
