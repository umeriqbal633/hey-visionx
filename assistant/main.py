"""VisionX entry point. Run from the project folder:  python -m assistant.main"""
from __future__ import annotations

import sys
from typing import Any, Protocol

from assistant.core.brain import Brain
from assistant.core.config import LOG_FILE, load_config
from assistant.core.confirm import confirm
from assistant.core.logger import ActionLogger
from assistant.core.providers import get_provider
from assistant.core.providers.base import BrainError
from assistant.core.registry import Registry, discover
from assistant.interfaces.text_io import TextIO

EXIT_WORDS = {"exit", "quit", "bye", "stop", "band karo", "khuda hafiz", "allah hafiz"}


class IO(Protocol):
    def say(self, text: str) -> None: ...
    def ask(self, question: str) -> str: ...


def missing_params(schema: dict[str, Any], params: dict[str, Any]) -> list[str]:
    return [p for p in schema.get("required", []) if not str(params.get(p, "")).strip()]


def handle(command: str, brain: Brain, registry: Registry, io: IO, logger: ActionLogger) -> str:
    """Process one command end to end and return the reply that was shown."""
    decision = brain.decide(command)
    skill = registry.get(decision.skill) if decision.skill else None

    if skill is None:
        reply = decision.reply or "Sorry, I didn't catch that."
        io.say(reply)
        logger.log(command=command, skill=None, params=None, confirmed=None, ok=True, reply=reply)
        return reply

    params = decision.params
    missing = missing_params(skill.parameters, params)
    if missing:
        reply = f"I need the {', '.join(missing)} to do that."
        io.say(reply)
        logger.log(command=command, skill=skill.name, params=params, confirmed=None, ok=False, reply=reply)
        return reply

    confirmed: bool | None = None
    if skill.risk == "confirm":
        confirmed = confirm(skill.confirm_prompt(**params), io.ask)
        if not confirmed:
            reply = "Okay, cancelled."
            io.say(reply)
            logger.log(command=command, skill=skill.name, params=params, confirmed=False, ok=False, reply=reply)
            return reply

    try:
        result = skill.run(**params)
    except Exception:  # a broken skill must never crash the assistant
        reply = f"Something went wrong while running {skill.name}."
        io.say(reply)
        logger.log(command=command, skill=skill.name, params=params, confirmed=confirmed, ok=False, reply=reply)
        return reply

    io.say(result.reply)
    logger.log(command=command, skill=skill.name, params=params, confirmed=confirmed,
               ok=result.ok, reply=result.reply)
    return result.reply


def main() -> int:
    config = load_config()
    io = TextIO(config.assistant_name)
    try:
        provider = get_provider(config)
    except BrainError as e:
        io.say(str(e))
        return 1

    registry = discover(config)
    brain = Brain(provider, registry, config.assistant_name, config.company)
    logger = ActionLogger(LOG_FILE)

    io.say(f"Hi, I'm {config.assistant_name}. Type a command, or 'exit' to quit.")
    while True:
        command = io.listen()
        if command is None or command.lower() in EXIT_WORDS:
            io.say("Bye!")
            return 0
        if command:
            handle(command, brain, registry, io, logger)


if __name__ == "__main__":
    sys.exit(main())
