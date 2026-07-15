from __future__ import annotations

import logging

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from config import Settings


logger = logging.getLogger(__name__)


async def start_timer(page: Page, settings: Settings) -> None:
    logger.info("Preparing timer entry for project %s", settings.timer_project)
    await select_project(page, settings.timer_project, settings.login_timeout)
    await fill_task(page, settings.timer_task, settings.login_timeout)
    await click_start_timer(page, settings.login_timeout)
    logger.info("Timer start requested")


async def stop_timer_if_running(page: Page, settings: Settings) -> bool:
    stop_selectors = (
        "[data-testid='stop-timer']",
        "[data-test='stop-timer']",
        "button:has-text('Stop Timer')",
        "button:has-text('Stop')",
        "[role='button']:has-text('Stop Timer')",
        "[role='button']:has-text('Stop')",
    )
    for selector in stop_selectors:
        try:
            button = page.locator(selector).first
            if await button.is_visible(timeout=2500):
                logger.info("Stopping timer using selector %s", selector)
                await button.click()
                await page.wait_for_load_state("networkidle", timeout=settings.login_timeout)
                return True
        except Exception:
            continue

    logger.info("No visible stop timer control found; timer may already be stopped")
    return False


async def select_project(page: Page, project_name: str, timeout: int) -> None:
    if await _is_visible(page, f"text={project_name}", timeout=2000):
        logger.info("Project %s is already visible/selected", project_name)
        return

    dropdown_selectors = (
        "[data-testid='project-select']",
        "[data-test='project-select']",
        "label:has-text('PROJECT') + *",
        "[role='combobox']",
        "button:has-text('Select project')",
        "button:has-text('Project')",
        "select[name*='project' i]",
    )
    for selector in dropdown_selectors:
        try:
            dropdown = page.locator(selector).first
            if await dropdown.is_visible(timeout=2500):
                await dropdown.click()
                await click_project_option(page, project_name, timeout)
                logger.info("Selected project %s", project_name)
                return
        except Exception:
            continue

    raise RuntimeError(f"Could not find project dropdown for {project_name!r}")


async def click_project_option(page: Page, project_name: str, timeout: int) -> None:
    option_selectors = (
        f"[role='option']:has-text('{project_name}')",
        f"li:has-text('{project_name}')",
        f"button:has-text('{project_name}')",
        f"text={project_name}",
    )
    for selector in option_selectors:
        try:
            option = page.locator(selector).first
            if await option.is_visible(timeout=timeout):
                await option.click()
                return
        except Exception:
            continue
    raise RuntimeError(f"Could not find project option {project_name!r}")


async def fill_task(page: Page, task_text: str, timeout: int) -> None:
    task_selectors = (
        "[data-testid='task-input']",
        "[data-test='task-input']",
        "input[placeholder*='working' i]",
        "textarea[placeholder*='working' i]",
        "input[name*='task' i]",
        "textarea[name*='task' i]",
        "[contenteditable='true']",
    )
    for selector in task_selectors:
        try:
            field = page.locator(selector).first
            if await field.is_visible(timeout=2500):
                await field.fill(task_text)
                logger.info("Filled timer task input")
                return
        except Exception:
            continue
    raise RuntimeError("Could not find task input")


async def click_start_timer(page: Page, timeout: int) -> None:
    start_selectors = (
        "[data-testid='start-timer']",
        "[data-test='start-timer']",
        "button:has-text('Start Timer')",
        "button:has-text('Start')",
        "[role='button']:has-text('Start Timer')",
        "[role='button']:has-text('Start')",
    )
    for selector in start_selectors:
        try:
            button = page.locator(selector).first
            if await button.is_visible(timeout=2500):
                await button.click()
                try:
                    await page.wait_for_load_state("networkidle", timeout=timeout)
                except PlaywrightTimeoutError:
                    logger.warning("Timed out waiting for networkidle after timer start")
                return
        except Exception:
            continue
    raise RuntimeError("Could not find start timer button")


async def _is_visible(page: Page, selector: str, timeout: int) -> bool:
    try:
        return await page.locator(selector).first.is_visible(timeout=timeout)
    except Exception:
        return False
