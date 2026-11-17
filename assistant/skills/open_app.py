"""Open an allowlisted desktop app from config/apps.yaml."""
from __future__ import annotations

import os

from assistant.core.matching import find_entry, join_or, suggest
from assistant.skills.base import Ask, Result, Skill


def _launch(target: str) -> None:
    os.startfile(target)  # Windows: works for .exe paths and URIs like "calculator:"


class OpenApp(Skill):
    name = "open_app"
    parameters = {
        "type": "object",
        "properties": {
            "app": {"type": "string", "description": "The app name in English, e.g. 'chrome'."}
        },
        "required": ["app"],
    }
    risk = "safe"

    def __init__(self, config) -> None:
        super().__init__(config)
        known = ", ".join(sorted(config.apps)) or "none yet"
        self.description = (
            "Open a desktop application on the user's PC. "
            f"Apps you can open: {known}. "
            "If the user names another app, still call this with that name; it will tell them it isn't set up."
        )

    def check(self, app: str = "", **_) -> str | Ask | None:
        """Unknown app: suggest a close name as a question (answered via follow-up), never open it."""
        if find_entry(self.config.apps, app) is not None:
            return None
        close = suggest(app, [(k, (v or {}).get("aliases") or []) for k, v in self.config.apps.items()])
        if len(close) == 1:
            return Ask(f"Did you mean {close[0]}?", {"app": close[0]})
        if close:
            return f"Did you mean {join_or(close[:3])}?"
        return f"I don't have '{app}' in my app list yet, so please add it to apps.yaml."

    def describe(self, app: str = "", **_) -> str:
        match = find_entry(self.config.apps, app)
        return f"open {match[0] if match else app}"

    def run(self, app: str = "", **_) -> Result:
        match = find_entry(self.config.apps, app)
        if match is None:
            question = self.check(app=app)
            return Result(False, getattr(question, "text", question) or "I couldn't find that app.")
        key, entry = match
        target = str(entry.get("target", "")).strip()
        if not target:
            return Result(False, f"{key} has no target in apps.yaml.")
        try:
            _launch(target)
        except OSError:
            return Result(False, f"I couldn't open {key}; it may not be installed.")
        return Result(True, f"Opening {key}.")
