"""WhatsApp groups from config/groups.yaml: load and find matches. Never guesses.

`name` must be the group's name exactly as WhatsApp shows it: VisionX searches WhatsApp for it
and only sends once the open chat is that exact group."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from assistant.core.matching import join_or, normalize, suggest


@dataclass(frozen=True)
class Group:
    name: str
    aliases: tuple[str, ...] = ()
    # When WhatsApp has two groups with this exact name: False = send nothing (default);
    # True = use the most recently active one (the user's choice, per group).
    pick_newest: bool = False

    def names(self) -> list[str]:
        return [self.name, *self.aliases]


def parse_groups(data: Any) -> list[Group]:
    entries = (data or {}).get("groups") or [] if isinstance(data, dict) else []
    groups = []
    for entry in entries:
        if not isinstance(entry, dict) or not str(entry.get("name") or "").strip():
            continue
        aliases = entry.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]
        newest = str(entry.get("duplicates") or "").strip().lower() == "newest"
        groups.append(Group(str(entry["name"]).strip(), tuple(str(a) for a in aliases), newest))
    return groups


def load_groups(path: Path) -> list[Group] | None:
    """None if the file doesn't exist. BaseLoader keeps names like 'C10' or '2024' as text."""
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return parse_groups(yaml.load(f, Loader=yaml.BaseLoader))


def find_groups(groups: list[Group] | None, spoken: str) -> list[Group]:
    wanted = normalize(spoken)
    if not wanted or not groups:
        return []
    return [g for g in groups if any(normalize(n) == wanted for n in g.names())]


def suggested_group(groups: list[Group] | None, spoken: str) -> str | None:
    """The one close-but-not-exact group name, if exactly one (for 'Did you mean X?')."""
    if not groups or find_groups(groups, spoken):
        return None
    close = suggest(spoken, [(g.name, g.aliases) for g in groups])
    return close[0] if len(close) == 1 else None


def resolve_group(groups: list[Group] | None, spoken: str) -> tuple[Group | None, str | None]:
    """(group, None) for exactly one match, else (None, one-sentence question)."""
    if groups is None:
        return None, "I don't have a groups list yet, so please copy groups.example.yaml to groups.yaml."
    matches = find_groups(groups, spoken)
    if not matches:
        close = suggest(spoken, [(g.name, g.aliases) for g in groups])[:3]
        if close:
            return None, f"Did you mean the group {join_or(close)}?"
        return None, f"I don't have a group called '{spoken}', so please add it to groups.yaml."
    if len(matches) > 1:
        return None, f"Which group do you mean: {join_or([g.name for g in matches])}?"
    return matches[0], None
