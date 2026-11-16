"""Match a spoken name against an allowlist from a YAML file (name + aliases)."""
from __future__ import annotations

import re
from typing import Any


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)   # drop punctuation (unicode-aware)
    return re.sub(r"\s+", " ", text).strip()


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
