"""Provider interface. Each LLM provider is one file in this package that defines
`create(config) -> Provider`. The provider name in settings.yaml is the file name."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class BrainError(Exception):
    """A provider failure, already phrased as one short sentence for the user."""


@dataclass
class ProviderResponse:
    tool_name: str | None = None
    tool_input: dict[str, Any] = field(default_factory=dict)
    text: str | None = None


class Provider(ABC):
    @abstractmethod
    def choose(self, system: str, tools: list[dict[str, Any]], command: str) -> ProviderResponse:
        """Send one command with the tool list; return a tool call or a text reply.
        Raise BrainError (with a one-sentence message) on any API failure."""
