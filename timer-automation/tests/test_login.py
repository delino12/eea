from __future__ import annotations

import pytest

from config import Settings
from login import confirm_authenticated, perform_login


class FakeLocator:
    def __init__(self, visible: bool = True) -> None:
        self.first = self
        self.visible = visible
        self.filled: list[str] = []
        self.clicks = 0

    async def wait_for(self, state: str, timeout: int) -> None:
        return None

    async def fill(self, value: str) -> None:
        self.filled.append(value)

    async def click(self) -> None:
        self.clicks += 1

    async def is_visible(self, timeout: int) -> bool:
        return self.visible


class FakeLoginPage:
    def __init__(self, authenticated: bool = True) -> None:
        self.url = "https://example.test/login"
        self.email = FakeLocator()
        self.password = FakeLocator()
        self.submit = FakeLocator()
        self.authenticated = authenticated

    async def goto(self, url: str, wait_until: str, timeout: int) -> None:
        self.url = url

    async def wait_for_load_state(self, state: str, timeout: int) -> None:
        return None

    async def wait_for_url(self, predicate, timeout: int) -> None:
        self.url = "https://example.test/dashboard"

    def locator(self, selector: str) -> FakeLocator:
        if "password" in selector:
            return self.password
        if "submit" in selector or "Log in" in selector:
            return self.submit
        return self.email


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


@pytest.mark.asyncio
async def test_perform_login_fills_credentials_and_submits(monkeypatch) -> None:
    page = FakeLoginPage()
    monkeypatch.setattr("login.is_session_authenticated", lambda page: _async_true())

    await perform_login(page, _settings())

    assert page.email.filled == ["user@example.test"]
    assert page.password.filled == ["secret"]
    assert page.submit.clicks == 1


@pytest.mark.asyncio
async def test_confirm_authenticated_raises_when_auth_not_confirmed(monkeypatch) -> None:
    page = FakeLoginPage()
    page.url = "https://example.test/login"
    monkeypatch.setattr("login.is_session_authenticated", lambda page: _async_false())

    with pytest.raises(RuntimeError, match="authenticated state"):
        await confirm_authenticated(page, _settings())


async def _async_true() -> bool:
    return True


async def _async_false() -> bool:
    return False
