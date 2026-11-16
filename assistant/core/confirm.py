"""Read back risky actions and only proceed on an explicit yes."""
from __future__ import annotations

from typing import Callable

from assistant.core.matching import normalize

# Latin spellings plus the same words in Urdu script (speech-to-text may return either).
YES_WORDS = frozenset({"yes", "y", "haan", "han", "ji", "haan ji",
                       "ہاں", "جی", "ہاں جی"})


# Voice mode only: how speech-to-text writes a spoken "ji" / "haa" (seen in the 2026-11-17
# voice test). "Huh" is deliberately NOT here; it's ambiguous, so it cancels.
VOICE_YES_WORDS = frozenset({"g", "gee", "jee", "ہا"})


def is_yes(answer: str | None, extra: frozenset[str] = frozenset()) -> bool:
    """True only for an explicit yes. Anything else (including empty) cancels."""
    word = normalize(answer or "")
    return word in YES_WORDS or word in extra


def confirm(prompt: str, ask: Callable[[str], str], extra_yes: frozenset[str] = frozenset(),
            hint: str = "(yes/no)") -> bool:
    """Ask `prompt` via the IO's ask() and return whether the user said yes."""
    try:
        answer = ask(f"{prompt} {hint}")
    except (EOFError, KeyboardInterrupt):
        return False
    return is_yes(answer, extra_yes)
