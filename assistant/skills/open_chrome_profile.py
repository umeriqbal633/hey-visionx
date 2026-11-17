"""Open Google Chrome in a specific profile (account), optionally with a website or search."""
from __future__ import annotations

import subprocess

from assistant.core.chrome_profiles import load_profiles, resolve_profile, suggested_profile, user_data_dir
from assistant.skills.base import Ask, Result, Skill
from assistant.skills.open_website import resolve_url


def _launch(args: list[str]) -> None:
    subprocess.Popen(args, close_fds=True)  # argument list, no shell


class OpenChromeProfile(Skill):
    name = "open_chrome_profile"
    description = (
        "Open Google Chrome in one of the user's Chrome profiles (a specific account or email), "
        "optionally with a website or a Google search in it. Use when the user names an account, "
        "profile or email for the browser, e.g. 'Umer wale Chrome mein YouTube kholo', "
        "'ali123 wala browser kholo', 'open my work profile'. Without a named profile/account, "
        "use open_website or open_app instead."
    )
    parameters = {
        "type": "object",
        "properties": {
            "profile": {
                "type": "string",
                "description": "The words the user used for the profile/account (name or email), as said.",
            },
            "site": {
                "type": ["string", "null"],   # models may send null for "no site"
                "description": "Optional website name (e.g. 'youtube') or text to search Google for.",
            },
        },
        "required": ["profile"],
    }
    risk = "safe"

    def _profiles(self):
        setting = self.config.settings.get("chrome", {}).get("user_data_dir")
        return load_profiles(user_data_dir(setting))

    def check(self, profile: str = "", **_) -> str | Ask | None:
        profiles = self._profiles()
        _, question = resolve_profile(profiles, profile)
        suggestion = suggested_profile(profiles, profile) if question else None
        return Ask(question, {"profile": suggestion.name}) if suggestion else question

    def run(self, profile: str = "", site: str = "", **_) -> Result:
        found, question = resolve_profile(self._profiles(), profile)
        if found is None:
            return Result(False, question or "I couldn't find that Chrome profile.")
        chrome = str((self.config.apps.get("chrome") or {}).get("target", "")).strip()
        if not chrome:
            return Result(False, "Chrome isn't in apps.yaml, so I can't open a profile.")
        args = [chrome, f"--profile-directory={found.directory}"]
        label = ""
        site = (site or "").strip()
        if site:
            url, label, is_search = resolve_url(self.config.websites, site)
            args.append(url)
            label = f"Google search for {label}" if is_search else label
        try:
            _launch(args)
        except OSError:
            return Result(False, "I couldn't start Chrome.")
        if label:
            return Result(True, f"Opening {label} in {found.label}.")
        return Result(True, f"Opening Chrome with {found.label}.")
