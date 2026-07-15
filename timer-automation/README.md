# Timer Automation

Playwright-based weekday login/logout automation for `https://timer.dev.webforxtech.com`.

The automation logs in, opens `/timer`, selects the configured project, fills the configured task, starts the timer, stops it at `LOGOUT_TIME`, logs out, and emails a report.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

Fill `.env` with real credentials and SMTP values. Do not commit `.env`.

## Run Manually

Login, start the configured timer entry, keep the browser open until `LOGOUT_TIME`, then stop and log out:

```bash
python app.py --action=login
```

Stop the timer if it is running, then log out using the persisted Playwright session state:

```bash
python app.py --action=logout
```

Run APScheduler:

```bash
python app.py --action=scheduler
```

The scheduler registers weekday jobs in `Africa/Lagos`: login/start timer at `09:00`, stop/logout at `LOGOUT_TIME` from `.env` (`18:00` by default). In scheduler mode, the same browser page is kept open between login and logout.

## Cron Alternative

Install with `crontab -e` after replacing paths with your deployment path:

```cron
0 9 * * 1-5  /path/to/timer-automation/.venv/bin/python /path/to/timer-automation/app.py --action=login
0 18 * * 1-5 /path/to/timer-automation/.venv/bin/python /path/to/timer-automation/app.py --action=logout
```

A copy is provided in `crontab.sample`. Prefer `python app.py --action=scheduler` when you want one browser session to remain open all day.

## Docker

```bash
docker build -t timer-automation .
docker run --rm --env-file .env -v "$PWD/logs:/app/logs" timer-automation
```

For non-headless operation in Docker, you need an X server or VNC-capable runtime and `HEADLESS=false`.

## Configuration

```dotenv
APP_URL=https://timer.dev.webforxtech.com
LOGIN_PATH=/login
LOGIN_EMAIL=
LOGIN_PASSWORD=
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
EMAIL_FROM=
EMAIL_TO=
EMAIL_CC=
HEADLESS=true
LOGIN_TIMEOUT=30000
LOGOUT_TIME=18:00
TIMER_PROJECT=Web Forx Technology
TIMER_TASK=Start work today on Webforx Technologies - Edusuc | Lafabah | Iyaloja | Webforx Website Review
```

`EMAIL_TO` and `EMAIL_CC` accept comma-separated addresses.

## Logs and Artifacts

Logs go to `logs/app.log`. Failure screenshots and `storage_state.json` are also written under `logs/`.

## Tests

```bash
pytest
```

The test suite uses mocks for Playwright and SMTP; it does not contact the timer site.

## Troubleshooting

If login fails after a UI change, inspect the failure screenshot in `logs/screenshots/` and update the email, password, submit, or authenticated-state selectors in `login.py`.

If timer start/stop fails, inspect the screenshot and update selectors in `timer.py`.

If logout fails, inspect the screenshot and update profile menu or logout selectors in `logout.py`.

If Chromium fails to start on Ubuntu, rerun `playwright install chromium` and confirm required system packages are installed. The Dockerfile includes the expected Ubuntu 24.04 browser dependencies.

If SMTP fails, the app logs the failure and continues shutdown. Check `SMTP_HOST`, `SMTP_PORT`, credentials, and whether your provider requires app passwords or IP allowlisting.
