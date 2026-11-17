"""VisionX entry point. Run from the project folder:

    python -m assistant.main          # voice mode (push-to-talk)
    python -m assistant.main --text   # typed mode
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Any, Protocol

from assistant.core.brain import Brain, Decision
from assistant.core.config import LOG_FILE, Config, load_config
from assistant.core.confirm import confirm, is_yes
from assistant.core.logger import ActionLogger
from assistant.core.matching import normalize
from assistant.core.providers import get_provider
from assistant.core.providers.base import BrainError
from assistant.core.registry import Registry, discover
from assistant.core.timing import Timings
from assistant.interfaces.text_io import TextIO
from assistant.skills.base import Ask

EXIT_WORDS = {"exit", "quit", "bye", "stop", "band karo", "khuda hafiz", "allah hafiz"}


class IO(Protocol):
    def say(self, text: str) -> None: ...
    def ask(self, question: str) -> str: ...


@dataclass
class Outcome:
    reply: str
    needs_answer: bool = False   # VisionX asked a question; the next input is the answer
    on_yes: Decision | None = None   # for "Did you mean X?": run this directly if the answer is yes


def missing_params(schema: dict[str, Any], params: dict[str, Any]) -> list[str]:
    return [p for p in schema.get("required", []) if not str(params.get(p, "")).strip()]


def with_follow_up(original: str, question: str, answer: str) -> str:
    """The text sent to the brain when the user answers VisionX's question."""
    return (f"{original}\n(You asked: \"{question}\" The user answered: \"{answer}\". "
            f"Now carry out the original command using this answer.)")


def handle(command: str, brain: Brain, registry: Registry, io: IO, logger: ActionLogger,
           timings: Timings | None = None, decision: Decision | None = None, **log_extra: Any) -> Outcome:
    """Process one command end to end. Pass `decision` to skip the brain (a confirmed suggestion)."""
    timings = timings or Timings()

    def log(skill: str | None, params: dict | None, confirmed: bool | None, ok: bool, reply: str) -> None:
        logger.log(command=command, skill=skill, params=params, confirmed=confirmed, ok=ok, reply=reply,
                   timings=timings.as_dict(), **log_extra)

    if decision is None:
        with timings.step("brain"):
            decision = brain.decide(command)
    skill = registry.get(decision.skill) if decision.skill else None

    if skill is None:
        reply = decision.reply or "Sorry, I didn't catch that."
        io.say(reply)
        log(None, None, None, True, reply)
        return Outcome(reply, needs_answer=reply.rstrip().endswith("?"))

    params = decision.params
    missing = missing_params(skill.parameters, params)
    if missing:
        reply = f"What {' and '.join(missing)} should I use?"
        io.say(reply)
        log(skill.name, params, None, False, reply)
        return Outcome(reply, needs_answer=True)

    with timings.step("check"):
        try:
            question = skill.check(**params)
        except Exception:
            question = f"Something went wrong while preparing {skill.name}."
    on_yes = None
    if isinstance(question, Ask):
        if question.on_yes:
            on_yes = Decision(skill=skill.name, params={**params, **question.on_yes})
        question = question.text
    if question:
        io.say(question)
        log(skill.name, params, None, False, question)
        return Outcome(question, needs_answer=question.rstrip().endswith("?"), on_yes=on_yes)

    confirmed: bool | None = None
    if skill.risk == "confirm":
        confirmed = confirm(skill.confirm_prompt(**params), io.ask,   # waiting time not counted
                            extra_yes=getattr(io, "extra_yes", frozenset()),
                            hint=getattr(io, "confirm_hint", "(yes/no)"))
        if not confirmed:
            reply = "Okay, cancelled."
            io.say(reply)
            log(skill.name, params, False, False, reply)
            return Outcome(reply)

    with timings.step("skill"):
        try:
            result = skill.run(**params)
        except Exception:  # a broken skill must never crash the assistant
            result = None
    if result is None:
        reply = f"Something went wrong while running {skill.name}."
        io.say(reply)
        log(skill.name, params, confirmed, False, reply)
        return Outcome(reply)

    io.say(result.reply)
    log(skill.name, params, confirmed, result.ok, result.reply)
    return Outcome(result.reply)


class Session:
    """The main loop: one optional follow-up answer per question, then it is cleared."""

    def __init__(self, io: Any, brain: Brain, registry: Registry, logger: ActionLogger,
                 show_timings: bool = True) -> None:
        self.io, self.brain, self.registry, self.logger = io, brain, registry, logger
        self.show_timings = show_timings
        # (original command, VisionX's question, what to run on a yes)
        self.pending: tuple[str, str, Decision | None] | None = None

    def step(self, text: str, timings: Timings | None = None) -> Outcome:
        timings = timings or Timings()
        if self.pending:
            original, question, on_yes = self.pending
            self.pending = None
            said_yes = is_yes(text, getattr(self.io, "extra_yes", frozenset()))
            if said_yes:
                text = "yes"                  # e.g. a spoken "ji" transcribed as "G."
            command = with_follow_up(original, question, text)
            # "Did you mean X?" + yes: run the suggestion directly; otherwise ask the brain.
            outcome = handle(command, self.brain, self.registry, self.io, self.logger, timings,
                             decision=on_yes if said_yes else None, follow_up=True)
            # One follow-up only: a second question is not chained.
        else:
            outcome = handle(text, self.brain, self.registry, self.io, self.logger, timings)
            if outcome.needs_answer:
                self.pending = (text, outcome.reply, outcome.on_yes)
        if self.show_timings and hasattr(self.io, "note"):
            self.io.note(timings.summary())
        return outcome

    def run(self) -> int:
        while True:
            timings = Timings()
            try:
                text = self.io.listen(timings)
            except KeyboardInterrupt:
                text = None
            if text is None or normalize(text) in EXIT_WORDS:
                self.io.say("Bye!")
                return 0
            if text:
                self.step(text, timings)


def build_voice_io(config: Config) -> Any:
    from assistant.interfaces.audio import Recorder
    from assistant.interfaces.hotkey import PushToTalk
    from assistant.interfaces.stt import get_transcriber
    from assistant.interfaces.tts import Speaker
    from assistant.interfaces.voice_io import VoiceIO

    s = config.settings
    hotkey = s.get("hotkey", "ctrl+alt+space")
    audio = s.get("audio", {})
    tts = s.get("tts", {})
    transcriber, notices = get_transcriber(config)
    if transcriber.primary is None:
        raise RuntimeError("No speech-to-text provider is available, so please use --text mode.")
    io = VoiceIO(PushToTalk(hotkey), Recorder(), transcriber,
                 Speaker(voice=tts.get("voice"), rate=tts.get("rate")),
                 assistant_name=config.assistant_name, hotkey_label=hotkey,
                 min_seconds=float(audio.get("min_seconds", 0.3)), beeps=bool(audio.get("beeps", True)))
    for n in notices:
        io.note(f"{config.assistant_name}: {n}")
    io.ptt.start()
    if s.get("stt", {}).get("local", {}).get("preload", True):
        transcriber.warm_up()
    return io


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m assistant.main", description="VisionX assistant")
    parser.add_argument("--text", action="store_true", help="typed mode instead of voice")
    args = parser.parse_args(argv)

    config = load_config()
    text_io = TextIO(config.assistant_name)
    try:
        provider = get_provider(config)
    except BrainError as e:
        text_io.say(str(e))
        return 1

    if args.text:
        io: Any = text_io
        hint = "Type a command, or 'exit' to quit."
    else:
        try:
            io = build_voice_io(config)
        except Exception as e:
            text_io.say(str(e) if isinstance(e, RuntimeError) else
                        "I couldn't start voice mode, so please run with --text.")
            return 1
        hint = f"Hold {config.settings.get('hotkey', 'ctrl+alt+space')} and speak; say 'exit' or press Ctrl+C to quit."

    registry = discover(config)
    brain = Brain(provider, registry, config.assistant_name, config.company)
    registry.attach(brain)
    session = Session(io, brain, registry, ActionLogger(LOG_FILE),
                      show_timings=bool(config.settings.get("show_timings", True)))
    io.say(f"Hi, I'm {config.assistant_name}.")
    if hasattr(io, "note"):
        io.note(hint)
    return session.run()


if __name__ == "__main__":
    sys.exit(main())
