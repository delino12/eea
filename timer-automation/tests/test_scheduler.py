from __future__ import annotations

from pathlib import Path

from config import TIMEZONE, Settings
from scheduler import create_scheduler, cron_entries


def _settings() -> Settings:
    return Settings(
        app_url="https://example.test",
        login_email="user@example.test",
        login_password="secret",
        smtp_host="smtp.example.test",
        smtp_port=587,
        smtp_username="smtp-user",
        smtp_password="smtp-secret",
        email_from="from@example.test",
        email_to=("to@example.test",),
        email_cc=(),
        headless=True,
        login_timeout=30000,
        logout_time="18:00",
    )


async def _job() -> None:
    return None


def test_create_scheduler_registers_weekday_jobs() -> None:
    scheduler = create_scheduler(_settings(), _job, _job)

    jobs = {job.id: job for job in scheduler.get_jobs()}

    assert set(jobs) == {"weekday_login", "weekday_logout"}
    assert jobs["weekday_login"].trigger.timezone == TIMEZONE
    assert jobs["weekday_logout"].trigger.timezone == TIMEZONE
    assert "hour='9'" in str(jobs["weekday_login"].trigger)
    assert "hour='18'" in str(jobs["weekday_logout"].trigger)


def test_cron_entries_are_literal_commands() -> None:
    entries = cron_entries(Path("/opt/timer-automation"), "/opt/timer-automation/.venv/bin/python")

    assert "0 9 * * 1-5  /opt/timer-automation/.venv/bin/python /opt/timer-automation/app.py --action=login" in entries
    assert "0 18 * * 1-5 /opt/timer-automation/.venv/bin/python /opt/timer-automation/app.py --action=logout" in entries
