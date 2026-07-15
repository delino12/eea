from __future__ import annotations

import os

import pytest

from config import ConfigError, load_settings


REQUIRED_ENV = {
    "APP_URL": "https://example.test",
    "LOGIN_EMAIL": "user@example.test",
    "LOGIN_PASSWORD": "secret",
    "SMTP_HOST": "smtp.example.test",
    "SMTP_PORT": "2525",
    "SMTP_USERNAME": "smtp-user",
    "SMTP_PASSWORD": "smtp-secret",
    "EMAIL_FROM": "from@example.test",
    "EMAIL_TO": "to@example.test,ops@example.test",
    "EMAIL_CC": "cc@example.test",
    "HEADLESS": "false",
    "LOGIN_TIMEOUT": "12345",
    "LOGOUT_TIME": "17:30",
}


def test_load_settings_parses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "environ", REQUIRED_ENV.copy())

    settings = load_settings(validate=True)

    assert settings.app_url == "https://example.test"
    assert settings.timer_url == "https://example.test/timer"
    assert settings.smtp_port == 2525
    assert settings.email_to == ("to@example.test", "ops@example.test")
    assert settings.email_cc == ("cc@example.test",)
    assert settings.headless is False
    assert settings.login_timeout == 12345
    assert settings.logout_time == "17:30"


def test_load_settings_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    env = REQUIRED_ENV.copy()
    env.pop("LOGIN_PASSWORD")
    monkeypatch.setattr(os, "environ", env)

    with pytest.raises(ConfigError, match="LOGIN_PASSWORD"):
        load_settings(validate=True)
