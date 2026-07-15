from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage

from config import Settings, TIMEZONE


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunReport:
    execution_date: datetime
    login_time: datetime | None
    logout_time: datetime | None
    total_runtime: str | None
    success: bool
    status: str
    exception_details: str | None = None
    screenshot_path: str | None = None


class EmailService:
    def __init__(self, settings: Settings, smtp_factory: type[smtplib.SMTP] = smtplib.SMTP) -> None:
        self.settings = settings
        self.smtp_factory = smtp_factory

    def send_report(self, report: RunReport) -> bool:
        message = self._build_message(report)
        recipients = list(self.settings.email_to + self.settings.email_cc)
        try:
            logger.info("Sending report email to %s", ", ".join(recipients))
            with self.smtp_factory(self.settings.smtp_host, self.settings.smtp_port, timeout=30) as smtp:
                smtp.starttls()
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
                smtp.send_message(message, from_addr=self.settings.email_from, to_addrs=recipients)
            logger.info("Report email sent")
            return True
        except Exception:
            logger.exception("SMTP report delivery failed")
            return False

    def _build_message(self, report: RunReport) -> EmailMessage:
        subject_status = "Success" if report.success else "Failed"
        message = EmailMessage()
        message["Subject"] = f"Timer Automation - {subject_status}"
        message["From"] = self.settings.email_from
        message["To"] = ", ".join(self.settings.email_to)
        if self.settings.email_cc:
            message["Cc"] = ", ".join(self.settings.email_cc)

        lines = [
            f"Execution date: {_format_dt(report.execution_date)}",
            f"Login time: {_format_dt(report.login_time)}",
            f"Logout time: {_format_dt(report.logout_time)}",
            f"Total runtime: {report.total_runtime or 'N/A'}",
            f"Status: {report.status}",
            f"Success: {report.success}",
        ]
        if report.exception_details:
            lines.append(f"Exception details: {report.exception_details}")
        if report.screenshot_path:
            lines.append(f"Screenshot path: {report.screenshot_path}")

        message.set_content("\n".join(lines))
        return message


def _format_dt(value: datetime | None) -> str:
    if value is None:
        return "N/A"
    if value.tzinfo is None:
        value = value.replace(tzinfo=TIMEZONE)
    return value.astimezone(TIMEZONE).isoformat(timespec="seconds")
