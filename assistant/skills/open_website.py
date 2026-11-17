"""Open an allowlisted website from config/websites.yaml, or search Google for anything else.

Only two kinds of URL are ever opened: a URL written in websites.yaml, or
https://www.google.com/search?q=<encoded text>. Whatever the LLM passes, it never
becomes a URL by itself.
"""
from __future__ import annotations

import re
import webbrowser
from urllib.parse import quote_plus

from assistant.core.matching import find_entry
from assistant.skills.base import Result, Skill

GOOGLE_SEARCH = "https://www.google.com/search?q="


def _strip_url_bits(text: str) -> str:
    """'https://www.youtube.com/' -> 'youtube' so a pasted domain still matches the allowlist."""
    t = text.strip().lower()
    t = re.sub(r"^[a-z]+://", "", t)
    t = re.sub(r"^www\.", "", t)
    t = t.rstrip("/")
    return re.sub(r"\.(com|org|net|ai|io|pk)$", "", t)


def _open(url: str) -> None:
    webbrowser.open(url)


class OpenWebsite(Skill):
    name = "open_website"
    parameters = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "A website name (e.g. 'youtube') or the text to search Google for.",
            }
        },
        "required": ["target"],
    }
    risk = "safe"

    def __init__(self, config) -> None:
        super().__init__(config)
        known = ", ".join(sorted(config.websites)) or "none yet"
        self.description = (
            "Open a website in the browser, or search Google. "
            f"Websites you can open directly: {known}. "
            "For anything else (other sites, questions, things to look up), pass the search text "
            "and it will be searched on Google."
        )

    def run(self, target: str = "", **_) -> Result:
        target = (target or "").strip()
        if not target:
            return Result(False, "Which website should I open?")
        url, label, is_search = resolve_url(self.config.websites, target)
        _open(url)
        return Result(True, f"Searching Google for {label}." if is_search else f"Opening {label}.")


def resolve_url(websites: dict, target: str) -> tuple[str, str, bool]:
    """(url, label, is_search). Only an allowlisted URL or a Google search URL, never anything else."""
    match = find_entry(websites, target) or find_entry(websites, _strip_url_bits(target))
    if match:
        key, entry = match
        url = str((entry or {}).get("url", "")).strip()
        if url:
            return url, key, False
    return GOOGLE_SEARCH + quote_plus(target), target, True
