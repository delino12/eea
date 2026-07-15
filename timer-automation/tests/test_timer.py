from __future__ import annotations

import pytest

from config import Settings
from timer import start_timer, stop_timer_if_running


class FakeLocator:
    def __init__(self, visible: bool = True) -> None:
        self.first = self
        self.visible = visible
        self.clicks = 0
        self.filled: list[str] = []
        self.selected_labels: list[str] = []

    async def is_visible(self, timeout: int) -> bool:
        return self.visible

    async def click(self, **kwargs) -> None:
        self.clicks += 1

    async def fill(self, value: str) -> None:
        self.filled.append(value)

    async def select_option(self, label: str) -> None:
        self.selected_labels.append(label)

    async def dispatch_event(self, event_name: str) -> None:
        return None

    async def scroll_into_view_if_needed(self, timeout: int) -> None:
        return None


class FakeTimerPage:
    def __init__(self, project_visible: bool = True, stop_visible: bool = True) -> None:
        self.project_text = FakeLocator(project_visible)
        self.native_project_select = FakeLocator(True)
        self.project_dropdown = FakeLocator(False)
        self.task_input = FakeLocator(True)
        self.start_button = FakeLocator(True)
        self.stop_button = FakeLocator(stop_visible)

    def locator(self, selector: str) -> FakeLocator:
        lowered = selector.lower()
        if selector == "text=Web Forx Technology":
            return self.project_text
        if lowered.startswith("select") or " + select" in lowered:
            return self.native_project_select
        if "project-select" in lowered or "combobox" in lowered or "select project" in lowered:
            return self.project_dropdown
        if "task-input" in lowered or "working" in lowered or "name*='task'" in lowered:
            return self.task_input
        if "start-timer" in lowered or "start timer" in lowered or "has-text('start')" in lowered:
            return self.start_button
        if "stop-timer" in lowered or "stop timer" in lowered or "has-text('stop')" in lowered:
            return self.stop_button
        return FakeLocator(False)

    async def wait_for_load_state(self, state: str, timeout: int) -> None:
        return None


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
async def test_start_timer_fills_task_and_clicks_start() -> None:
    page = FakeTimerPage(project_visible=True)

    await start_timer(page, _settings())

    assert page.native_project_select.selected_labels == ["Web Forx Technology"]
    assert page.project_dropdown.clicks == 0
    assert page.task_input.filled == [
        "Start work today on Webforx Technologies - Edusuc | Lafabah | Iyaloja | Webforx Website Review"
    ]
    assert page.start_button.clicks == 1


@pytest.mark.asyncio
async def test_stop_timer_clicks_stop_when_visible() -> None:
    page = FakeTimerPage(stop_visible=True)

    stopped = await stop_timer_if_running(page, _settings())

    assert stopped is True
    assert page.stop_button.clicks == 1


@pytest.mark.asyncio
async def test_stop_timer_returns_false_when_no_stop_button() -> None:
    page = FakeTimerPage(stop_visible=False)

    stopped = await stop_timer_if_running(page, _settings())

    assert stopped is False
