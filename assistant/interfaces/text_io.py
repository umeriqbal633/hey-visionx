"""Phase 1 interface: typed input, printed output."""
from __future__ import annotations


def clean(text: str) -> str:
    """Strip whitespace and invisible byte-order marks (PowerShell adds one to piped input)."""
    return text.replace("﻿", "").strip()


class TextIO:
    def __init__(self, assistant_name: str = "VisionX") -> None:
        self.name = assistant_name

    def note(self, text: str) -> None:
        print(text)

    def listen(self, timings=None) -> str | None:
        """Next command, or None when the user is done (Ctrl+Z/Ctrl+D or Ctrl+C)."""
        try:
            return clean(input("You: "))
        except (EOFError, KeyboardInterrupt):
            print()
            return None

    def say(self, text: str) -> None:
        print(f"{self.name}: {text}")

    def ask(self, question: str) -> str:
        self.say(question)
        return clean(input("You: "))
