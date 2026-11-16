"""The brain: sends a command + skill schemas to the LLM and gets back a skill + args,
or a one-sentence reply (a clarifying question, or 'I can't do that')."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from assistant.core.providers.base import BrainError, Provider
from assistant.core.registry import Registry

SYSTEM_PROMPT = """\
You are {name}, a desktop assistant on the user's Windows PC{by_company}.

The user gives short commands in English, Urdu (اردو), or Roman Urdu mixed with English.
Examples: "chrome kholo" = open Chrome; "youtube chalao" = open YouTube;
"time kya hua hai" / "kitne baje hain" = what time is it; "biryani recipe search karo" = search Google for biryani recipe.

How to respond:
- If a tool fits the command, call exactly one tool. Pass names and search text in plain English
  (for example "chrome", not "chrome kholo"), except keep the user's own words for search queries.
- Only use the tools you are given. You cannot run shell commands or anything outside them.
- Never guess. If the command is unclear or missing something, reply with one short question.
- If no tool fits, say in one short sentence what you can help with.
- Every text reply is one short sentence, in the same language style the user used.
"""


@dataclass
class Decision:
    skill: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    reply: str | None = None


class Brain:
    def __init__(self, provider: Provider, registry: Registry, assistant_name: str = "VisionX",
                 company: str = "") -> None:
        self.provider = provider
        self.registry = registry
        # Built once and never changed, so it stays byte-identical for prompt caching.
        self.system = SYSTEM_PROMPT.format(
            name=assistant_name, by_company=f", made by {company}" if company else ""
        )

    def decide(self, command: str) -> Decision:
        try:
            response = self.provider.choose(self.system, self.registry.tool_schemas(), command)
        except BrainError as e:
            return Decision(reply=str(e))

        if response.tool_name:
            if self.registry.get(response.tool_name) is None:
                return Decision(reply="I don't have a skill for that yet.")
            return Decision(skill=response.tool_name, params=response.tool_input)
        return Decision(reply=response.text or "Sorry, I didn't catch that.")
