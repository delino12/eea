from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from browser import BrowserFactory
from config import Settings


def _settings(tmp_path) -> Settings:
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
        storage_state_path=tmp_path / "state.json",
        screenshot_dir=tmp_path / "screens",
        log_dir=tmp_path,
    )


@pytest.mark.asyncio
async def test_browser_session_launches_context_and_cleans_up(monkeypatch, tmp_path) -> None:
    page = object()
    context = MagicMock()
    context.close = AsyncMock()
    context.new_page = AsyncMock(return_value=page)
    context.set_default_timeout.return_value = None
    browser = AsyncMock()
    browser.new_context = AsyncMock(return_value=context)
    chromium = AsyncMock()
    chromium.launch = AsyncMock(return_value=browser)
    playwright = AsyncMock()
    playwright.chromium = chromium

    starter = AsyncMock(return_value=playwright)
    fake_async_playwright = AsyncMock()
    fake_async_playwright.start = starter
    monkeypatch.setattr("browser.async_playwright", lambda: fake_async_playwright)

    async with BrowserFactory(_settings(tmp_path)).session(use_storage_state=False) as session:
        assert session.page is page

    chromium.launch.assert_awaited_once_with(headless=True)
    browser.new_context.assert_awaited_once()
    context.close.assert_awaited_once()
    browser.close.assert_awaited_once()
    playwright.stop.assert_awaited_once()
