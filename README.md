# VisionX

A desktop assistant for Windows by VisionX Intelligence. You type (and later speak)
commands in English, Urdu or Roman Urdu, and VisionX opens apps, websites and more.

**Status:** Phase 4 (voice with push-to-talk, or typed: open apps, open websites / Google
search, Chrome profiles, tell the time, WhatsApp messages to contacts and groups, chats,
scheduled tasks).

## Setup (once)

Requires Windows and Python 3.11+ (developed on 3.14).

```powershell
cd "C:\Users\pc\Desktop\Hey VisionX"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
notepad .env
```

In `.env` (in the project folder, next to `.env.example`, never in `.env.example` itself),
add your keys and save:

- `GROQ_API_KEY=` (free, https://console.groq.com): the brain currently runs on Groq
  (`provider: groq` in `assistant/config/settings.yaml`).
- `VISIONX_ANTHROPIC_KEY=` (https://console.anthropic.com): to use Claude Haiku instead,
  add this key and change that line to `provider: anthropic`.

> Never rename it to `ANTHROPIC_API_KEY`. Claude Code reads that name and would bill the
> API key instead of your Claude Pro plan.

For WhatsApp, install WhatsApp Desktop from the Microsoft Store, log in, then create your
contacts file (it is git-ignored; only the example is committed):

```powershell
copy assistant\config\contacts.example.yaml assistant\config\contacts.yaml
notepad assistant\config\contacts.yaml
```

Replace the two fake entries with real ones. Numbers can be written as `0300 1234567`,
`03001234567` or `+92 300 1234567`.

For voice mode, Windows also needs the Microsoft Visual C++ Redistributable (free):
`winget install Microsoft.VCRedist.2015+.x64`.

## Run

```powershell
cd "C:\Users\pc\Desktop\Hey VisionX"
.\.venv\Scripts\python.exe -m assistant.main          # voice mode
.\.venv\Scripts\python.exe -m assistant.main --text   # typed mode
```

**Voice mode:** hold **Ctrl+Alt+Space**, speak, release. You hear a beep when recording
starts and stops. VisionX prints what it heard, does it, and speaks a short reply. When it
asks something ("Which Ali?"), just answer; you don't need to repeat the command. For a
WhatsApp read-back, say **yes** or **ji**. Say `exit` or press Ctrl+C to quit.

**Typed mode:** type a command and press Enter. Type `exit` (or `bye`, `band karo`) to quit.

While testing, each command shows a timing line (recording, speech-to-text, brain, skill).
Turn it off with `show_timings: false` in `settings.yaml`.

To check how speech-to-text writes your voice (Latin vs Urdu script), record a few clips and
compare settings: `.\.venv\Scripts\python.exe -m assistant.tools.stt_script_test --local`.

Example commands:

| You type | VisionX does |
|---|---|
| `chrome kholo` | Opens Chrome |
| `open calculator` | Opens Calculator |
| `youtube chalao` | Opens youtube.com |
| `lahore ka mausam search karo` | Google search |
| `time kya hua hai` | Tells the time |
| `Ali ko message bhejo ke main late hoon` | Reads it back, and on "haan" sends it in WhatsApp |
| `Sara ki chat kholo` | Opens your WhatsApp chat with Sara |
| `Umer wale Chrome mein YouTube kholo` | Opens YouTube in that Chrome profile (matched by name or email) |

If a name is close but not exact ("Saad Atak"), VisionX asks "Did you mean Saad Attock?";
just answer yes or no. If it matches nobody, or more than one contact (two "Ali"s), it asks
instead of guessing.

**WhatsApp groups:** groups have no phone number, so list them in `groups.yaml` (git-ignored):

```powershell
copy assistant\config\groups.example.yaml assistant\config\groups.yaml
notepad assistant\config\groups.yaml
```

Write each group's `name` exactly as WhatsApp shows it (spaces, brackets, emojis), plus
`aliases` you'd say. Then: `C10 group mein bhejo ke class 8 baje hai`. VisionX reads it back,
and after your yes it searches WhatsApp for the group, opens it, checks the open chat is exactly
that group, types the message (line breaks kept, `@all` becomes WhatsApp's "mention all
members") and presses Send. It brings WhatsApp to the front and clicks into the message box, so
don't use the mouse or keyboard for those few seconds. If the group already has unsent text,
or the chat that opens isn't exactly that group, nothing is sent. Group messages can be
scheduled like any other command (`har roz 7:50 pe C10 group mein link bhejo`).

**Scheduled tasks:** add a time or repetition to any command and VisionX schedules it:

| You say | VisionX does |
|---|---|
| `har roz subah 9 baje Saad ko good morning bhejo` | Every day at 9:00 AM sends that WhatsApp |
| `every weekday at 8:30 YouTube kholo` | Mon–Fri at 8:30 AM opens YouTube |
| `kal shaam 5 baje Saad ko message karo ke main aa raha hoon` | Once, tomorrow at 5:00 PM |
| `har Monday aur Thursday raat 9 baje calculator kholo` | Weekly on those days |
| `mere scheduled tasks batao` | Lists them, numbered |
| `9 baje wala task delete karo` / `task 2 delete karo` | Deletes one (asks yes/no first) |

VisionX reads the whole schedule back once; your yes approves every future run (scheduled
WhatsApp messages are sent without asking again). Tasks run through Windows Task Scheduler
(folder "VisionX"), even when VisionX isn't open; if the PC was off or asleep, the task runs
as soon as it's back on. You need to be logged in; a WhatsApp send that can't be verified
(e.g. locked screen) is left typed and logged as not sent.

**WhatsApp auto-send:** after your yes, VisionX checks that WhatsApp's message box holds exactly
your message, clicks Send, and says "Sent" only once the box is empty; otherwise it leaves the
message typed and tells you. Turn it off
with `auto_send: false` under `whatsapp:` in `settings.yaml`.

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
| `settings.yaml` | Assistant name, LLM provider/model, hotkey, speech-to-text, voice |
| `apps.yaml` | Apps VisionX may open: name, aliases, `.exe` path or URI |
| `websites.yaml` | Sites opened directly; everything else becomes a Google search |
| `contacts.yaml` | Your contacts: name, aliases, phone (git-ignored; see `contacts.example.yaml`) |
| `groups.yaml` | Your WhatsApp groups: exact name, aliases (git-ignored; see `groups.example.yaml`) |
| `corrections.yaml` | Words speech-to-text keeps getting wrong → what you meant (git-ignored; see `corrections.example.yaml`) |

**Teaching VisionX your voice:** when it mishears the same word again and again (check the
`You (voice): ...` line), add it to `corrections.yaml`, e.g. `gronkolo: chrome kholo`.

VisionX only opens what is listed in these files. To add an app, add an entry to
`apps.yaml` (find Store apps' URIs or paths with `Get-StartApps` in PowerShell).

Every action is logged to `assistant/logs/actions.jsonl` (not committed). The log includes
WhatsApp message text and contact names, so it stays on this PC.

## Adding a skill

Create one file in `assistant/skills/` with a `Skill` subclass (`name`, `description`,
`parameters` JSON schema, `risk` = `"safe"` or `"confirm"`, and `run(**params) -> Result`;
optionally `check(**params)` to ask a question before the read-back, and `confirm_prompt`),
plus a test in `assistant/tests/`. It's picked up automatically; no core changes.

## Cost

Right now everything is free: the brain and speech-to-text run on Groq's free tier, with
offline speech-to-text (faster-whisper) as a fallback and Windows voices for speech. Switching
the brain to Claude Haiku (`provider: anthropic`) costs roughly $1/month for personal use.
