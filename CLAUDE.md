# Personal Assistant Agent

## What this is
A voice-controlled desktop assistant, like Siri, that does my daily tasks on my computer:
open apps and websites, send WhatsApp messages, call contacts, run coding tasks in my
projects through Claude Code, and set reminders.

Personal use first. It is built so it can become a product later, so keep it clean and
configurable.

- Assistant name: **VisionX** (by VisionX Intelligence)
- Wake word (Phase 5): **"Hey VisionX"**
- Both still come from `config/settings.yaml`, never hardcoded, so they can change later.

## Cost rule
The only paid part is the brain: Anthropic API with Claude Haiku (about $1/month for my
use). Everything else must be free or run locally. If any other step would need payment,
stop and tell me first.

| Part | Choice |
|---|---|
| Brain (LLM) | Anthropic API, `claude-haiku-5-5` (paid, cheap). Groq free tier as a backup provider |
| Speech-to-text | faster-whisper running locally; Groq Whisper free tier as a faster option |
| Text-to-speech | Piper or pyttsx3, both local |
| Wake word | openWakeWord, trained on my own phrase (personal use only) |
| WhatsApp / calls | WhatsApp Desktop deep links, `tel:` links to Phone Link |
| Coding skill | Claude Code on my Claude Pro plan (never the API key) |

Use prompt caching for the system prompt and skill list, since they're the same on every
command. Handle API errors and rate limits gracefully: tell me in one sentence and don't crash.

## API key safety (important)
Claude Code switches to paid API billing instead of my Pro plan if it sees an
`ANTHROPIC_API_KEY` environment variable. So:
- Store VisionX's key in `.env` as `VISIONX_ANTHROPIC_KEY`, never as `ANTHROPIC_API_KEY`.
- Pass it to the Anthropic client explicitly (`Anthropic(api_key=...)`). Don't rely on env auto-detection.
- When the coding skill starts `claude`, build its environment from a copy of `os.environ`
  with `ANTHROPIC_API_KEY` and `VISIONX_ANTHROPIC_KEY` removed.
- Add a test that checks the coding skill's subprocess environment has neither variable.

## Owner context
- Primary OS: Windows (check the actual OS at the start of a session and tell me if it's different)
- Python 3.11+
- I give commands in English, Urdu, or Roman Urdu mixed with English ("chrome kholo",
  "Ali ko message bhejo ke main late hoon"). The brain must handle all three.

## Architecture
Input → (speech-to-text) → Brain → Skill → Reply (printed now, spoken from Phase 3)

```
.env                      # API keys only, never committed (repo root; .env.example ships)
assistant/
  main.py                 # entry point: the main loop  (run: python -m assistant.main)
  core/
    brain.py              # sends the command + skill schemas to the LLM, gets back skill + args
    providers/            # one file per LLM provider; anthropic.py first
    registry.py           # auto-discovers skills in skills/
    confirm.py            # read back risky actions, wait for yes/no
    logger.py             # appends every action to logs/actions.jsonl
    config.py             # loads YAML + .env (dotenv_values: never copied into os.environ)
    matching.py           # name/alias lookup against the YAML allowlists
    phone.py              # number normalization to E.164 (PK formats) + display format
    contacts.py           # contacts.yaml loading (BaseLoader: numbers stay strings) + matching
    groups.py             # groups.yaml loading + matching (WhatsApp groups, exact names)
    script.py             # Devanagari / Urdu / Latin detection; speakable() for TTS
    corrections.py        # corrections.yaml: misheard word -> intended word (voice only)
    chrome_profiles.py    # reads Chrome's "Local State" (read-only) to match profiles by name/email
    schedules.py          # scheduled task model, parsing, schedules.yaml, Task Scheduler XML
    scheduler_windows.py  # schtasks create/delete/query (argument lists, no shell)
  run_task.py             # what Windows runs at a task's time: python -m assistant.run_task <id>
    timing.py             # per-step timings (rec, stt, brain, check, skill)
  skills/
    base.py               # Skill base class
    open_app.py           # one file per skill
    _whatsapp.py          # shared helpers; a leading "_" keeps a module out of skill discovery
  interfaces/             # NOT "io/": that would shadow Python's built-in io module
    text_io.py            # Phase 1: typed input (--text)
    voice_io.py           # Phase 3: push-to-talk in, spoken + printed out
    audio.py              # mic recorder (16 kHz mono) + beeps
    hotkey.py             # push-to-talk key state machine + pynput wiring
    stt/                  # one file per STT provider: groq.py (default), local.py (faster-whisper)
                          #   __init__.py = fallback chain + Devanagari guard
    tts.py                # pyttsx3 (Windows voices); speaks an English-readable version
    wake.py               # Phase 5: wake word
  tools/
    stt_script_test.py    # record clips, compare STT language settings (python -m assistant.tools.stt_script_test)
  config/
    settings.yaml         # assistant name, provider, model, voice, hotkey
    apps.yaml             # spoken name + aliases -> executable path or URI
    websites.yaml         # name + aliases -> URL; anything else = google.com/search?q= only
    contacts.yaml         # list of name + aliases + phone (git-ignored; contacts.example.yaml committed)
    groups.yaml           # WhatsApp groups: exact name + aliases (git-ignored; groups.example.yaml committed)
    corrections.yaml      # personal speech fixes (git-ignored; corrections.example.yaml committed)
    schedules.yaml        # scheduled tasks (git-ignored; schedules.example.yaml committed)
    projects.yaml         # name + aliases -> folder path
  logs/
  tests/
```

## Skill contract
Every skill defines:
- `name` and `description` (the LLM reads the description to decide when to use it)
- `parameters` as a JSON schema
- `risk`: `"safe"` or `"confirm"`
- `run(**params) -> Result(ok: bool, reply: str)` where `reply` is one short sentence to show or speak
- optional `check(**params) -> str | Ask | None`: runs before the read-back; return a question
  (unknown or ambiguous contact, etc.) to stop and ask instead of guessing. For a single
  close match return `Ask("Did you mean X?", on_yes={...})`: if the user says yes, the same
  skill runs with those params (no brain call); risky skills still do their read-back.
- optional `confirm_prompt(**params) -> str`: the read-back sentence for `risk: "confirm"`

Adding a skill means adding one file in `skills/`. No changes to core code.

## Rules
1. The brain is provider-agnostic. Provider and model come from `config/settings.yaml`.
   Default: Anthropic, `claude-haiku-5-5`, using tool use. Write the provider layer so
   Groq, Ollama or OpenAI can be added as one new file each.
2. The LLM never runs raw shell commands. It can only call registered skills, and skills
   only act on allowlisted items from the YAML config files.
3. Skills with `risk: "confirm"` (send message, call, git push, delete anything) must read
   the action back and wait for an explicit yes. If a contact, app or project isn't in
   config, ask. Never guess.
4. Secrets live only in `.env`. `.env` and `logs/` are in `.gitignore`. Ship a `.env.example`.
5. Log every action (timestamp, raw command, skill, params, confirmed?, result) to
   `logs/actions.jsonl`.
6. Replies are short: one sentence.
7. Every skill has tests with external calls mocked (LLM, app launching, URLs). Run
   `pytest` and make it pass before calling a phase done.
8. Keep dependencies minimal and pinned in `requirements.txt`.
9. Before writing code for a phase, show me a short plan and the file list, and wait for my OK.

## Phases
- [x] 0. Setup: tools installed, folder, git, this file
- [x] 1. Text brain + skill system + open_app / open_website / get_time
- [x] 2. WhatsApp message skill + contacts
- [x] 3. Voice: push-to-talk hotkey, speech-to-text, text-to-speech
- [x] 3.1 Accuracy (better STT, fuzzy "Did you mean", corrections, yes/no retry),
      Chrome profiles, WhatsApp auto-send
- [x] 4. Scheduled tasks (once / daily / weekdays / weekly) via Windows Task Scheduler
- [ ] 4b. Call skill, coding skill (Claude Code), reminders (moved out of Phase 4 by the user)
- [ ] 5. Wake word, system tray app, start on boot
- [ ] 6. Product prep (later)

## Environment notes
- Brain currently runs on **Groq** (`provider: groq`, model `openai/gpt-oss-120b`, reasoning_effort low)
  because there is no Anthropic key yet. Switch back to Haiku by setting `provider: anthropic`
  in settings.yaml; anthropic.py and its settings are unchanged. Groq key: `GROQ_API_KEY` in `.env`.
  Model chosen by a 10-command English/Roman Urdu/Urdu test (gpt-oss-20b reworded a message;
  llama-3.x models returned 404 for this key). Free tier limits for gpt-oss-120b per the Groq
  docs page (unlabeled plan): 30 RPM, 1K RPD, 8K TPM, 200K TPD.
- PC: i5-1235U (2P+8E cores), 16 GB RAM, Intel Iris Xe, no NVIDIA → local STT is CPU-only.
- Python 3.14 in `.venv`. All Phase 3 packages install on 3.14 (no 3.12 venv needed).
- **Smart App Control is ON** (keep it on). It blocks unsigned DLLs with little reputation:
  ctranslate2 4.9.0 is blocked, so **ctranslate2 is pinned to 4.8.5**. Check new binary
  packages for "An Application Control policy has blocked this file" before upgrading.
- Microsoft Visual C++ Redistributable 2015+ x64 (14.52) installed via winget (2026-11-17);
  the old 2017 runtime crashed faster-whisper and broke onnxruntime.
- faster-whisper 1.2.1 can't decode files with av 19; VisionX always passes numpy arrays.
- `claude` CLI is not on PATH yet (needed in Phase 4): `npm i -g @anthropic-ai/claude-code`.
- WhatsApp Desktop (Store, 5319275A.WhatsAppDesktop) is installed; the `whatsapp:` protocol is registered.
- Follow-ups: when VisionX asks a question (brain or skill check), the next input is sent to
  the brain together with the original command, once; then it's cleared.
- Confirmation accepts only: yes / y / haan / han / ji / haan ji (also in Urdu script:
  ہاں / جی / ہاں جی). **Voice mode only** also accepts how Whisper writes a spoken ji/haa:
  G / Gee / Jee / ہا (user decision 2026-11-17). A clear no (no/nahi/cancel/...) cancels at
  once; anything else gets one "Please say yes or no." retry, then cancels.

## Phase 3.1 decisions (2026-11-17, after a live voice session with ~50% misses)
- Misses were mostly speech-to-text, not the brain (brain got 10/10 typed and 7/7 Whisper
  transcripts). No fine-tuning; fixes target the "ears" and missing skills.
- STT: Groq `whisper-large-v3` (not turbo) + prompt v2 with "VisionX" and app names; on the
  8 saved clips this fixed Paim→Time, vijanx→VisionX, Huh→Haan, G→Jii, mein→main.
- A leading "Hey VisionX" (fuzzy) is stripped from transcripts; corrections.yaml is applied after.
- Fuzzy names are only ever **suggested** ("Did you mean Saad Attock?"); nothing acts on them
  without a yes. The brain must not ask about names itself; skills check them.
- Chrome profiles: matched locally on profile name, email username, or matching digits
  ("633"). Questions show only the profile name and last 3 characters of the account
  ("Muhammad (…633)"); full emails never go to the LLM. On this PC the …633 account is the
  **Default ("Muhammad")** profile; "Umer" is a different (…634) account.
- **WhatsApp auto-send is ON** (user decision 2026-11-17, reverses the Phase 2 "press Enter
  yourself" rule). First version (foreground check + Enter) failed live: it reported "Sent"
  but nothing was sent, because the deep link APPENDS to an existing unsent draft and a
  foreground check proves nothing. Current version (`_whatsapp.send_verified`) uses UI
  Automation (comtypes) on the "Type a message to …" box: Enter only if the box holds exactly
  the message (an old draft → don't send, tell the user), and "Sent" only once the box empties;
  otherwise "typed but not sent". `whatsapp.auto_send: false` turns it off. No unofficial APIs.
- Groq brain: optional tool params allow `null`; one retry on Groq's `tool_use_failed` 400.

## Voice (Phase 3) decisions
- `python -m assistant.main` = voice (hold Ctrl+Alt+Space), `--text` = typed mode.
- STT: Groq `whisper-large-v3-turbo` (≈0.2–0.6 s), fallback local faster-whisper `small` int8,
  8 threads. Benchmark on this CPU (3.5 s clip, language fixed): base 1.1 s, small 3.7 s
  (turbo not tested: too slow to download/run here). Small chosen for Urdu accuracy; it's only
  the fallback. Switch to `base` in settings.yaml if the fallback feels slow.
- Script: `stt.language: en` + a Roman Urdu `stt.prompt`. From the stt_script_test with 8 real
  clips: en+prompt and auto+prompt 8/8 Latin; auto alone gave Devanagari 2/8; en alone
  translated Roman Urdu to English. Devanagari guard: retry once with `ur`, else drop + ask to repeat.
- TTS: pyttsx3 (Zira). Piper not used: no Urdu voice, needs onnxruntime + model download.
  Non-Latin text (e.g. an Urdu-script WhatsApp message) is replaced in speech by "the message
  on screen"; the screen always shows the exact text that will be sent.
- Timings (`show_timings`): rec / stt / brain / check / skill and release→action (target < 3 s)
  are printed and logged to actions.jsonl.
- Git: push to `origin` (github.com/umeriqbal633/hey-visionx) once per finished phase.

## Phase 4 decisions: scheduled tasks (2026-11-17)
- Skills: `schedule_task` (confirm), `list_scheduled_tasks` (safe), `delete_scheduled_task` (confirm).
- At creation the command is turned into an exact skill call by the brain (`Registry.attach`
  gives skills `self.brain` / `self.registry`), checked like a normal command, and read back
  in full ("Every day at 9:00 AM: send 'good morning' to … on WhatsApp. Schedule it?").
  The plan is cached so the read-back and the saved task are identical.
- The yes approves every run (user decision): scheduled WhatsApp sends go out without asking.
- Storage: `config/schedules.yaml` (git-ignored) holds the approved skill + params; each task
  is also `VisionX\<id>` in Windows Task Scheduler (schtasks + XML, no admin, "Interactive
  only", StartWhenAvailable = run as soon as the PC is back on after a missed time).
- Windows runs `pythonw -m assistant.run_task <id>`: runs the stored skill (no LLM, no
  question), logs `"scheduled": true`, speaks a one-line result (`scheduler.announce`),
  removes one-time tasks afterwards. Scheduling skills can never be scheduled or run that way.
- Dates/days ("kal", "parson", weekday names incl. peer/jumma) are resolved by code, not the
  LLM. "9 baje" without AM/PM matches both 9 AM and 9 PM tasks and asks if both exist.
- Locked screen: a WhatsApp send that can't be verified is left typed and logged as not sent.

## WhatsApp groups (2026-11-19/20, tested live on one of the user's class groups, empty for testing)
- Skill `send_whatsapp_group` (confirm). Groups have no deep link, so `_whatsapp.send_to_group`
  drives WhatsApp Desktop through UI Automation; no unofficial APIs.
- Steps: put the exact name into "Search or start a new chat" with **LegacyIAccessible SetValue**
  (typed keys don't reach it; ValuePattern sets text without filtering) → pick the "Search
  results." row whose title starts with the exact name + space/end ("Class C1" ≠ "Class C10 (8 PM)")
  → open it with the row's DoDefaultAction (mouse click as fallback) → **the message box must be
  named exactly "Type a message to group <name>"** before anything is typed.
- Typing needs a **real mouse click** in the message box (UIA SetFocus alone: keys are lost) and
  WhatsApp in front. `bring_to_front` restores the window and taps Alt before
  SetForegroundWindow (opening `whatsapp:` alone doesn't beat Windows' focus lock). Every click
  first checks, via ElementFromPoint, that the spot is that element (matched by type + name: the
  UIA tree holds many copies of each element), so a covering window is never clicked.
- Line breaks are typed as Shift+Enter; `@all` is turned into a real mention by invoking the
  "all  Mention all members in this chat" button. Draft in the group → nothing sent; "Sent" only
  once the box empties (same as contacts). Text comparisons ignore spacing/line breaks.
- "C10 ko message bhejo" (a group name sent to the person skill) asks whether to use the group.
- While the search box holds text its accessible name is BLANK: find it as the unnamed edit box.
- Two WhatsApp groups can share a name (old batches): then nothing is sent (`ambiguous`), unless
  groups.yaml says `duplicates: newest` for that group (user's choice) → the first search result,
  i.e. the most recently active one.
- Scheduled tasks firing at the same minute take turns through a file lock
  (`core/runlock.py`, `logs/run_task.lock`, wait ≤ 5 min, then run anyway).
- The user's class-link schedules (2026-11-20): one weekday/weekly task per class group, sent
  10 minutes before class, message verbatim with @all. Real group names live only in
  groups.yaml / schedules.yaml (git-ignored).
- Next (planned, waiting for the user's data): class automation in steps: (1) classes.yaml with the
  fixed daily Meet link per class + students, link to the group before class, Meet attendance
  read from Chrome's People panel, private message to absent students; (2) WhatsApp voice call to
  absent students, message if no answer; (3) AI conversation on the call (needs a virtual audio
  cable, the user's OK, and a voice-language choice).

## Skill notes
- **open_website:** opens a URL from `websites.yaml`, otherwise only ever
  `https://www.google.com/search?q=<encoded text>`. No other URL is opened.
- **WhatsApp:** open `whatsapp://send?phone=<number without +>&text=<url-encoded text>` so
  WhatsApp Desktop opens with the message typed. Confirm before sending. Do not use
  unofficial WhatsApp libraries (whatsapp-web.js, Baileys, etc.).
  - `send_whatsapp` (confirm): read-back is exactly `Send '<message>' to <Name> (+92 300 1234567)?`.
    After the yes, auto-send presses Enter (see Phase 3.1 decisions); with auto_send off the
    user presses Enter.
  - `open_whatsapp_chat` (safe): same URL without `text`.
  - Message text is passed through verbatim (no translation); encode with `quote(safe="")`
    so spaces are `%20`, never `+`.
  - Contact lookup returns all matches: 0 → ask to add, 2+ → "Which Ali do you mean: …?". Never guess.
  - The contact list is never sent to the LLM; only the name the user said.
- **Calls:** open a `tel:+92...` URI. On Windows this goes to Phone Link with a paired phone.
- **Coding:** run `claude -p "<task>" --permission-mode acceptEdits --allowedTools "<scoped list>" --output-format json`
  with the working directory set to the project path from `projects.yaml`, and reply with the
  `result` summary. Only push after confirmation. Never use `--dangerously-skip-permissions`.
