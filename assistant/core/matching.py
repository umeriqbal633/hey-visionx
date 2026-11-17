"""Match a spoken name against an allowlist from a YAML file (name + aliases).

Exact matches act; close-but-not-exact matches are only ever *suggested* back to the user
("Did you mean Chrome?"). Nothing acts on a fuzzy match without the user's answer.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Iterable

FUZZY_CUTOFF = 0.72


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)   # drop punctuation (unicode-aware)
    return re.sub(r"\s+", " ", text).strip()


def compact(text: str) -> str:
    """Lowercase letters and digits only: 'ali123 @ gmail.com' -> 'ali123gmailcom'."""
    return re.sub(r"[\W_]+", "", (text or "").lower())


def find_entry(entries: dict[str, Any], spoken: str) -> tuple[str, dict[str, Any]] | None:
    """Return (key, entry) whose name or alias matches `spoken`, else None. Never guesses."""
    wanted = normalize(spoken)
    if not wanted:
        return None
    for key, entry in entries.items():
        entry = entry or {}
        names = [key, *(entry.get("aliases") or [])]
        if any(normalize(str(n)) == wanted for n in names):
            return key, entry
    return None


def similarity(spoken: str, name: str) -> float:
    """Best similarity between `name` and any run of words in `spoken` (0..1).
    'saad atak dad' vs 'saad attock' compares 'saad atak' too."""
    s_words, n = normalize(spoken).split(), normalize(name)
    if not s_words or not n:
        return 0.0
    width = len(n.split())
    best = SequenceMatcher(None, " ".join(s_words), n).ratio()
    for size in {max(1, width - 1), width, width + 1}:
        for i in range(0, max(1, len(s_words) - size + 1)):
            chunk = " ".join(s_words[i:i + size])
            best = max(best, SequenceMatcher(None, chunk, n).ratio())
    return best


def suggest(spoken: str, names: Iterable[tuple[str, Iterable[str]]],
            cutoff: float = FUZZY_CUTOFF) -> list[str]:
    """Keys whose name/aliases are close to `spoken`, best first. `names` = (key, [aliases...])."""
    scored = []
    for key, aliases in names:
        score = max(similarity(spoken, str(n)) for n in [key, *aliases])
        if score >= cutoff:
            scored.append((score, key))
    scored.sort(key=lambda x: -x[0])
    return [k for _, k in scored]


def join_or(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]
