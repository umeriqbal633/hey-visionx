"""Contacts from config/contacts.yaml: load, normalize numbers, find matches. Never guesses."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from assistant.core.matching import normalize
from assistant.core.phone import PhoneError, display_phone, normalize_phone


@dataclass(frozen=True)
class Contact:
    name: str
    aliases: tuple[str, ...]
    phone: str | None          # E.164, or None if the number in the file is invalid
    raw_phone: str = ""

    @property
    def display(self) -> str:
        return display_phone(self.phone) if self.phone else self.raw_phone

    def names(self) -> list[str]:
        return [self.name, *self.aliases]


def parse_contacts(data: Any) -> list[Contact]:
    entries = (data or {}).get("contacts") or [] if isinstance(data, dict) else []
    contacts = []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("name"):
            continue
        raw = str(entry.get("phone") or "").strip()
        try:
            phone = normalize_phone(raw)
        except PhoneError:
            phone = None
        aliases = entry.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]
        contacts.append(Contact(str(entry["name"]).strip(), tuple(str(a) for a in aliases), phone, raw))
    return contacts


def load_contacts(path: Path) -> list[Contact] | None:
    """None if the file doesn't exist. BaseLoader keeps every value a string, so a number
    like 03001234567 isn't misread by YAML as an (octal) integer."""
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return parse_contacts(yaml.load(f, Loader=yaml.BaseLoader))


def find_contacts(contacts: list[Contact], spoken: str) -> list[Contact]:
    """Every contact whose name or alias matches; the caller decides what 0 or 2+ means."""
    wanted = normalize(spoken)
    if not wanted:
        return []
    return [c for c in contacts if any(normalize(n) == wanted for n in c.names())]


def _join_or(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]


def resolve_contact(contacts: list[Contact] | None, spoken: str) -> tuple[Contact | None, str | None]:
    """(contact, None) when exactly one usable match, else (None, one-sentence question)."""
    if contacts is None:
        return None, "I don't have a contacts list yet, so please copy contacts.example.yaml to contacts.yaml."
    matches = find_contacts(contacts, spoken)
    if not matches:
        return None, f"I don't have '{spoken}' in my contacts, so please add them to contacts.yaml."
    if len(matches) > 1:
        return None, f"Which {spoken} do you mean: {_join_or([c.name for c in matches])}?"
    contact = matches[0]
    if not contact.phone:
        return None, f"{contact.name}'s number in contacts.yaml looks wrong, so please fix it."
    return contact, None
