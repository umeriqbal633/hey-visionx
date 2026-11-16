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
  skills/
    base.py               # Skill base class
    open_app.py           # one file per skill
  interfaces/             # NOT "io/": that would shadow Python's built-in io module
    text_io.py            # Phase 1: typed input
    stt.py, tts.py        # Phase 3: speech in/out
    wake.py               # Phase 5: wake word
  config/
    settings.yaml         # assistant name, provider, model, voice, hotkey
    apps.yaml             # spoken name + aliases -> executable path or URI
    websites.yaml         # name + aliases -> URL; anything else = google.com/search?q= only
    contacts.yaml         # name + aliases -> phone number (E.164, e.g. +923001234567)
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
- [ ] 2. WhatsApp message skill + contacts
- [ ] 3. Voice: push-to-talk hotkey, speech-to-text, text-to-speech
- [ ] 4. Call skill, coding skill (Claude Code), reminders
- [ ] 5. Wake word, system tray app, start on boot
- [ ] 6. Product prep (later)

## Environment notes
- Python 3.14 in `.venv`. If faster-whisper / openWakeWord lack 3.14 wheels in Phase 3/5, add a 3.12 venv.
- `claude` CLI is not on PATH yet (needed in Phase 4): `npm i -g @anthropic-ai/claude-code`.
- WhatsApp Desktop is not installed yet (needed in Phase 2); `apps.yaml` already points at `whatsapp:`.
- Confirmation accepts only: yes / y / haan / han / ji / haan ji. Anything else cancels.
- Git: push to `origin` (github.com/umeriqbal633/hey-visionx) once per finished phase.

## Skill notes
- **open_website:** opens a URL from `websites.yaml`, otherwise only ever
  `https://www.google.com/search?q=<encoded text>`. No other URL is opened.
- **WhatsApp:** open `whatsapp://send?phone=<number without +>&text=<url-encoded text>` so
  WhatsApp Desktop opens with the message typed. Confirm before sending. Do not use
  unofficial WhatsApp libraries (whatsapp-web.js, Baileys, etc.).
- **Calls:** open a `tel:+92...` URI. On Windows this goes to Phone Link with a paired phone.
- **Coding:** run `claude -p "<task>" --permission-mode acceptEdits --allowedTools "<scoped list>" --output-format json`
  with the working directory set to the project path from `projects.yaml`, and reply with the
  `result` summary. Only push after confirmation. Never use `--dangerously-skip-permissions`.
