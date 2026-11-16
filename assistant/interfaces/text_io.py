"""Phase 1 interface: typed input, printed output."""
from __future__ import annotations


class TextIO:
    def __init__(self, assistant_name: str = "VisionX") -> None:
        self.name = assistant_name

    def listen(self) -> str | None:
        """Next command, or None when the user is done (Ctrl+Z/Ctrl+D or Ctrl+C)."""
        try:
            return input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None

    def say(self, text: str) -> None:
        print(f"{self.name}: {text}")

    def ask(self, question: str) -> str:
        self.say(question)
        return input("You: ").strip()
