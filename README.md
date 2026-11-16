# VisionX

A desktop assistant for Windows by VisionX Intelligence. You type (and later speak)
commands in English, Urdu or Roman Urdu, and VisionX opens apps, websites and more.

**Status:** Phase 1 (typed commands: open apps, open websites / Google search, tell the time).

## Setup (once)

Requires Windows and Python 3.11+ (developed on 3.14).

```powershell
cd "C:\Users\pc\Desktop\Hey VisionX"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
notepad .env
```

In `.env`, paste your Anthropic API key after `VISIONX_ANTHROPIC_KEY=` and save. Get a key
at https://console.anthropic.com.

> Never rename it to `ANTHROPIC_API_KEY`. Claude Code reads that name and would bill the
> API key instead of your Claude Pro plan.

## Run

```powershell
cd "C:\Users\pc\Desktop\Hey VisionX"
.\.venv\Scripts\python.exe -m assistant.main
```

Type a command and press Enter. Type `exit` (or `bye`, `band karo`) to quit.

Example commands:

| You type | VisionX does |
|---|---|
| `chrome kholo` | Opens Chrome |
| `open calculator` | Opens Calculator |
| `youtube chalao` | Opens youtube.com |
| `lahore ka mausam search karo` | Google search |
| `time kya hua hai` | Tells the time |

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

All external calls (the LLM, launching apps, opening the browser) are mocked, so tests are
free and need no API key.

## Configuration

All in `assistant/config/`:

| File | What it holds |
|---|---|
| `settings.yaml` | Assistant name, LLM provider/model/effort, hotkey |
| `apps.yaml` | Apps VisionX may open: name, aliases, `.exe` path or URI |
| `websites.yaml` | Sites opened directly; everything else becomes a Google search |

VisionX only opens what is listed in these files. To add an app, add an entry to
`apps.yaml` (find Store apps' URIs or paths with `Get-StartApps` in PowerShell).

Every action is logged to `assistant/logs/actions.jsonl` (not committed).

## Adding a skill

Create one file in `assistant/skills/` with a `Skill` subclass (`name`, `description`,
`parameters` JSON schema, `risk` = `"safe"` or `"confirm"`, and `run(**params) -> Result`),
plus a test in `assistant/tests/`. It's picked up automatically; no core changes.

## Cost

Only the brain is paid: Claude Haiku via the Anthropic API (roughly $1/month for personal
use). The system prompt and skill list are prompt-cached. Everything else is free or local.
