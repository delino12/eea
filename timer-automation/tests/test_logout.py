from __future__ import annotations

import pytest

from config import Settings
from logout import perform_logout


class FakeLocator:
    def __init__(self, visible: bool) -> None:
        self.first = self
        self.visible = visible
        self.clicks = 0

    async def is_visible(self, timeout: int) -> bool:
        return self.visible

    async def click(self) -> None:
        self.clicks += 1


class FakeLogoutPage:
    def __init__(self, has_logout: bool = True) -> None:
        self.url = "https://example.test/timer"
        self.menu = FakeLocator(True)
        self.logout = FakeLocator(has_logout)

    def locator(self, selector: str) -> FakeLocator:
        if "logout" in selector.lower() or "log out" in selector.lower():
            return self.logout
        return self.menu

    async def wait_for_url(self, predicate, timeout: int) -> None:
        self.url = "https://example.test/login"


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
async def test_perform_logout_clicks_menu_and_logout() -> None:
    page = FakeLogoutPage()

    await perform_logout(page, _settings())

    assert page.menu.clicks == 1
    assert page.logout.clicks == 1
    assert page.url.endswith("/login")


@pytest.mark.asyncio
async def test_perform_logout_raises_when_logout_control_missing() -> None:
    page = FakeLogoutPage(has_logout=False)

    with pytest.raises(RuntimeError, match="Could not find logout control"):
        await perform_logout(page, _settings())
