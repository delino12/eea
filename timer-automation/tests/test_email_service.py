from __future__ import annotations

from datetime import datetime

from config import TIMEZONE, Settings
from email_service import EmailService, RunReport


class FakeSMTP:
    sent_messages: list[tuple[object, str, list[str]]] = []

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def starttls(self) -> None:
        return None

    def login(self, username: str, password: str) -> None:
        self.username = username
        self.password = password

    def send_message(self, message, from_addr: str, to_addrs: list[str]) -> None:
        self.sent_messages.append((message, from_addr, to_addrs))


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
        email_cc=("cc@example.test",),
        headless=True,
        login_timeout=30000,
        logout_time="18:00",
    )


def test_send_report_builds_subject_recipients_and_body() -> None:
    FakeSMTP.sent_messages.clear()
    report = RunReport(
        execution_date=datetime(2026, 7, 15, 9, 0, tzinfo=TIMEZONE),
        login_time=datetime(2026, 7, 15, 9, 1, tzinfo=TIMEZONE),
        logout_time=datetime(2026, 7, 15, 18, 0, tzinfo=TIMEZONE),
        total_runtime="8:59:00",
        success=False,
        status="Logout failed",
        exception_details="selector changed",
        screenshot_path="logs/screenshots/logout.png",
    )

    assert EmailService(_settings(), smtp_factory=FakeSMTP).send_report(report) is True

    message, from_addr, recipients = FakeSMTP.sent_messages[0]
    assert message["Subject"] == "Timer Automation - Failed"
    assert message["To"] == "to@example.test"
    assert message["Cc"] == "cc@example.test"
    assert from_addr == "from@example.test"
    assert recipients == ["to@example.test", "cc@example.test"]
    body = message.get_content()
    assert "Status: Logout failed" in body
    assert "Exception details: selector changed" in body
    assert "Screenshot path: logs/screenshots/logout.png" in body
