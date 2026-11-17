"""Skill contract. Adding a skill = adding one file in skills/ with a Skill subclass."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from assistant.core.config import Config


@dataclass(frozen=True)
class Result:
    ok: bool
    reply: str  # one short sentence to show or speak


@dataclass(frozen=True)
class Ask:
    """A question from check(). If `on_yes` is set (e.g. {"contact": "Saad Attock"} for
    'Did you mean Saad Attock?') and the user answers yes, the same skill runs again with
    these params merged in, without asking the brain."""
    text: str
    on_yes: dict[str, Any] | None = None


class Skill(ABC):
    name: ClassVar[str]
    description: str                     # the LLM reads this to decide when to use the skill
    parameters: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}
    risk: ClassVar[Literal["safe", "confirm"]] = "safe"

    def __init__(self, config: Config) -> None:
        self.config = config

    def check(self, **params: Any) -> "str | Ask | None":
        """Runs before any read-back. Return a one-sentence question (e.g. 'Which Ali do you
        mean?'), or an Ask with an `on_yes` suggestion, to stop and ask the user; or None to
        continue. Never guess."""
        return None

    def confirm_prompt(self, **params: Any) -> str:
        """Sentence read back before a risky action. Override for a clearer read-back."""
        return f"Should I run {self.name} with {params}?"

    def tool_schema(self) -> dict[str, Any]:
        """Provider-neutral tool definition."""
        return {"name": self.name, "description": self.description, "parameters": self.parameters}

    @abstractmethod
    def run(self, **params: Any) -> Result: ...
