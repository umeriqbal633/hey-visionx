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

    def find_site(self, target: str):
        return find_entry(self.config.websites, target) or find_entry(
            self.config.websites, _strip_url_bits(target)
        )

    def run(self, target: str = "", **_) -> Result:
        target = (target or "").strip()
        if not target:
            return Result(False, "Which website should I open?")
        match = self.find_site(target)
        if match:
            key, entry = match
            url = str(entry.get("url", "")).strip()
            if url:
                _open(url)
                return Result(True, f"Opening {key}.")
        _open(GOOGLE_SEARCH + quote_plus(target))
        return Result(True, f"Searching Google for {target}.")
