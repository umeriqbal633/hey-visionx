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


class Skill(ABC):
    name: ClassVar[str]
    description: str                     # the LLM reads this to decide when to use the skill
    parameters: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}
    risk: ClassVar[Literal["safe", "confirm"]] = "safe"

    def __init__(self, config: Config) -> None:
        self.config = config

    def confirm_prompt(self, **params: Any) -> str:
        """Sentence read back before a risky action. Override for a clearer read-back."""
        return f"Should I run {self.name} with {params}?"

    def tool_schema(self) -> dict[str, Any]:
        """Provider-neutral tool definition."""
        return {"name": self.name, "description": self.description, "parameters": self.parameters}

    @abstractmethod
    def run(self, **params: Any) -> Result: ...
