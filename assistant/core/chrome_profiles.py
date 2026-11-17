"""Chrome profiles, read from Chrome's own "Local State" file on this PC (read-only).

Profile names and emails are only used locally to match what the user said
("Umer wala Chrome", "ali123 wala browser"); they are never sent to the LLM.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from assistant.core.matching import compact, join_or, normalize, similarity

DEFAULT_USER_DATA = r"%LOCALAPPDATA%\Google\Chrome\User Data"
# Parts of addresses that say nothing about which profile is meant.
GENERIC_WORDS = frozenset({"com", "www", "gmail", "mail", "org", "net", "edu", "http", "https",
                           "chrome", "browser", "profile", "wala", "wale", "wali"})


@dataclass(frozen=True)
class Profile:
    directory: str      # e.g. "Profile 5" (what Chrome's --profile-directory wants)
    name: str           # display name, e.g. "Umer"
    email: str = ""

    def keys(self) -> list[str]:
        """Things the user might say for this profile."""
        local = self.email.split("@")[0] if self.email else ""
        return [k for k in (self.name, local, self.email) if k]

    @property
    def label(self) -> str:
        return f"the {self.name} profile"

    @property
    def hint(self) -> str:
        """Name plus the last 3 characters of the account, e.g. 'Muhammad (…633)'. Only these
        3 characters ever leave the PC (in follow-up text), never the full email."""
        local = self.email.split("@")[0] if self.email else ""
        return f"{self.name} (…{local[-3:]})" if len(local) >= 4 else self.name


def user_data_dir(setting: str | None = None) -> Path:
    return Path(os.path.expandvars(setting or DEFAULT_USER_DATA))


def load_profiles(data_dir: Path) -> list[Profile]:
    path = data_dir / "Local State"
    if not path.exists():
        return []
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    cache = (state.get("profile") or {}).get("info_cache") or {}
    return [Profile(d, str(info.get("name") or d), str(info.get("user_name") or ""))
            for d, info in sorted(cache.items())]


def find_profiles(profiles: list[Profile], spoken: str) -> list[Profile]:
    """Profiles whose name, email or email username appears in what the user said."""
    said = compact(spoken)
    if not said:
        return []
    said_words = set(normalize(spoken).split())
    hits = []
    for p in profiles:
        keys = [compact(k) for k in p.keys()]
        whole_key = any(len(k) >= 3 and k in said for k in keys)                    # 'ali123' in 'ali123gmailcom'
        name_word = any(len(w) >= 3 and w not in GENERIC_WORDS and w in said_words
                        for w in normalize(p.name).split())                       # 'umer' ~ 'Umer Work'
        if whole_key or name_word:
            hits.append(p)
    return hits


def close_profiles(profiles: list[Profile], spoken: str) -> list[Profile]:
    """Close-but-not-exact profiles, best first (up to 3), only near the best score so one
    clear winner isn't diluted. Scored on the name and the part before "@" only: the shared
    "@gmail.com" would make every gmail account look similar."""
    if not profiles:
        return []
    said_digits = set(re.findall(r"\d{3,}", spoken))

    def score(p: Profile) -> float:
        s = max(similarity(spoken, k) for k in p.keys()[:2])
        local = p.email.split("@")[0] if p.email else ""
        if said_digits & set(re.findall(r"\d{3,}", local)):   # "ali123" vs "…123": strong clue
            s = max(s, 0.9)
        return s

    scored = sorted(((score(p), p) for p in profiles), key=lambda x: -x[0])
    top = scored[0][0]
    return [p for s, p in scored if s >= 0.72 and s >= top - 0.15][:3]


def suggested_profile(profiles: list[Profile], spoken: str) -> Profile | None:
    """The single close profile for 'Did you mean X?', or None."""
    if find_profiles(profiles, spoken):
        return None
    close = close_profiles(profiles, spoken)
    return close[0] if len(close) == 1 else None


def resolve_profile(profiles: list[Profile], spoken: str) -> tuple[Profile | None, str | None]:
    """(profile, None) for exactly one match, else (None, one-sentence question). Never guesses."""
    if not profiles:
        return None, "I couldn't find any Chrome profiles on this PC."
    hits = find_profiles(profiles, spoken)
    if len(hits) == 1:
        return hits[0], None
    if len(hits) > 1:
        return None, f"Which Chrome profile do you mean: {join_or([p.hint for p in hits])}?"
    close = close_profiles(profiles, spoken)
    if close:
        return None, f"Did you mean the {join_or([p.hint for p in close])} Chrome profile?"
    names = join_or([p.name for p in profiles])
    return None, f"I don't know a Chrome profile called '{normalize(spoken)}'; you have {names}."
