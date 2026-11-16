"""Read back risky actions and only proceed on an explicit yes."""
from __future__ import annotations

from typing import Callable

from assistant.core.matching import normalize

YES_WORDS = frozenset({"yes", "y", "haan", "han", "ji", "haan ji"})


def is_yes(answer: str | None) -> bool:
    """True only for an explicit yes. Anything else (including empty) cancels."""
    return normalize(answer or "") in YES_WORDS


def confirm(prompt: str, ask: Callable[[str], str]) -> bool:
    """Ask `prompt` via the IO's ask() and return whether the user said yes."""
    try:
        answer = ask(f"{prompt} (yes/no)")
    except (EOFError, KeyboardInterrupt):
        return False
    return is_yes(answer)
