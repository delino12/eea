from __future__ import annotations

import pytest

from config import Settings
from logout import perform_logout


class FakeLocator:
    def __init__(self, visible: bool, on_click=None) -> None:
        self.first = self
        self.visible = visible
        self.clicks = 0
        self.on_click = on_click

    async def is_visible(self, timeout: int) -> bool:
        return self.visible

    async def scroll_into_view_if_needed(self, timeout: int) -> None:
        return None

    async def click(self, **kwargs) -> None:
        self.clicks += 1
        if self.on_click is not None:
            self.on_click()


class FakeLogoutPage:
    def __init__(self, has_direct_signout: bool = True, has_menu_logout: bool = True) -> None:
        self.url = "https://example.test/timer"
        self.menu_open = False
        self.menu = FakeLocator(True, on_click=self._open_menu)
        self.direct_signout = FakeLocator(has_direct_signout)
        self.menu_logout = FakeLocator(has_menu_logout)

    def _open_menu(self) -> None:
        self.menu_open = True

    def locator(self, selector: str) -> FakeLocator:
        lowered = selector.lower()
        if "user-menu" in lowered or "profile" in lowered or "account" in lowered or "avatar" in lowered:
            return self.menu
        if "sign" in lowered or "logout" in lowered or "log" in lowered:
            if self.direct_signout.visible:
                return self.direct_signout
            if self.menu_open:
                return self.menu_logout
            return self.direct_signout
        return self.menu

    async def wait_for_url(self, predicate, timeout: int) -> None:
        self.url = "https://example.test/login"

    async def evaluate(self, script: str) -> bool:
        return False


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
async def test_perform_logout_clicks_sidebar_signout() -> None:
    page = FakeLogoutPage()

    await perform_logout(page, _settings())

    assert page.menu.clicks == 0
    assert page.direct_signout.clicks == 1
    assert page.url.endswith("/login")


@pytest.mark.asyncio
async def test_perform_logout_falls_back_to_menu_logout() -> None:
    page = FakeLogoutPage(has_direct_signout=False, has_menu_logout=True)

    await perform_logout(page, _settings())

    assert page.menu.clicks == 1
    assert page.menu_logout.clicks == 1
    assert page.url.endswith("/login")


@pytest.mark.asyncio
async def test_perform_logout_raises_when_logout_control_missing() -> None:
    page = FakeLogoutPage(has_direct_signout=False, has_menu_logout=False)

    with pytest.raises(RuntimeError, match="Could not find logout control"):
        await perform_logout(page, _settings())
