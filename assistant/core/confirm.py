"""Read back risky actions and only proceed on an explicit yes."""
from __future__ import annotations

from typing import Callable

from assistant.core.matching import normalize

# Latin spellings plus the same words in Urdu script (speech-to-text may return either).
YES_WORDS = frozenset({"yes", "y", "haan", "han", "ji", "haan ji",
                       "ہاں", "جی", "ہاں جی"})

# Voice mode only: how speech-to-text writes a spoken "ji" / "haa" (seen in the 2026-11-17
# voice test). "Huh" is deliberately NOT here; it's ambiguous, so it gets one retry.
VOICE_YES_WORDS = frozenset({"g", "gee", "jee", "ہا"})

# A clear no cancels immediately; anything that is neither yes nor no gets one retry.
NO_WORDS = frozenset({"no", "n", "nahi", "nahin", "nai", "na", "nope", "cancel", "mat", "mat karo",
                      "rehne do", "نہیں", "نہ"})

RETRY_PROMPT = "Please say yes or no."


def is_yes(answer: str | None, extra: frozenset[str] = frozenset()) -> bool:
    """True only for an explicit yes. Anything else (including empty) is not a yes."""
    word = normalize(answer or "")
    return word in YES_WORDS or word in extra


def is_no(answer: str | None) -> bool:
    return normalize(answer or "") in NO_WORDS


def confirm(prompt: str, ask: Callable[[str], str], extra_yes: frozenset[str] = frozenset(),
            hint: str = "(yes/no)") -> bool:
    """Ask `prompt`; yes -> True, clear no -> False, unclear -> ask once more, then cancel."""
    try:
        answer = ask(f"{prompt} {hint}")
        if is_yes(answer, extra_yes):
            return True
        if is_no(answer):
            return False
        return is_yes(ask(RETRY_PROMPT), extra_yes)
    except (EOFError, KeyboardInterrupt):
        return False
