from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
import os
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "logs"
STORAGE_STATE_PATH = LOG_DIR / "storage_state.json"
SCREENSHOT_DIR = LOG_DIR / "screenshots"
TIMEZONE_NAME = "Africa/Lagos"
TIMEZONE = ZoneInfo(TIMEZONE_NAME)


class ConfigError(ValueError):
    """Raised when required configuration is absent or invalid."""


@dataclass(frozen=True)
class Settings:
    app_url: str
    login_email: str
    login_password: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    email_from: str
    email_to: tuple[str, ...]
    email_cc: tuple[str, ...]
    headless: bool
    login_timeout: int
    logout_time: str
    login_path: str = "/login"
    storage_state_path: Path = STORAGE_STATE_PATH
    screenshot_dir: Path = SCREENSHOT_DIR
    log_dir: Path = LOG_DIR

    @property
    def timer_url(self) -> str:
        return f"{self.app_url.rstrip('/')}/timer"

    @property
    def login_url(self) -> str:
        return f"{self.app_url.rstrip('/')}/{self.login_path.strip('/')}"


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ConfigError(f"Invalid boolean value: {value!r}")


def _parse_recipients(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _require(env: dict[str, str], names: Iterable[str]) -> None:
    missing = [name for name in names if not env.get(name)]
    if missing:
        raise ConfigError(f"Missing required environment variables: {', '.join(missing)}")


def load_settings(env_file: str | Path | None = None, validate: bool = True) -> Settings:
    if env_file is not None:
        load_dotenv(dotenv_path=env_file, override=True)
    else:
        load_dotenv()

    env = dict(os.environ)
    required = (
        "APP_URL",
        "LOGIN_EMAIL",
        "LOGIN_PASSWORD",
        "SMTP_HOST",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "EMAIL_FROM",
        "EMAIL_TO",
    )
    if validate:
        _require(env, required)

    try:
        smtp_port = int(env.get("SMTP_PORT", "587"))
        login_timeout = int(env.get("LOGIN_TIMEOUT", "30000"))
    except ValueError as exc:
        raise ConfigError("SMTP_PORT and LOGIN_TIMEOUT must be integers") from exc

    settings = Settings(
        app_url=env.get("APP_URL", "https://timer.dev.webforxtech.com").rstrip("/"),
        login_path=env.get("LOGIN_PATH", "/login"),
        login_email=env.get("LOGIN_EMAIL", ""),
        login_password=env.get("LOGIN_PASSWORD", ""),
        smtp_host=env.get("SMTP_HOST", ""),
        smtp_port=smtp_port,
        smtp_username=env.get("SMTP_USERNAME", ""),
        smtp_password=env.get("SMTP_PASSWORD", ""),
        email_from=env.get("EMAIL_FROM", ""),
        email_to=_parse_recipients(env.get("EMAIL_TO")),
        email_cc=_parse_recipients(env.get("EMAIL_CC")),
        headless=_parse_bool(env.get("HEADLESS", "true")),
        login_timeout=login_timeout,
        logout_time=env.get("LOGOUT_TIME", "18:00"),
    )

    if validate and not settings.email_to:
        raise ConfigError("EMAIL_TO must contain at least one recipient")

    settings.log_dir.mkdir(parents=True, exist_ok=True)
    settings.screenshot_dir.mkdir(parents=True, exist_ok=True)
    return settings
