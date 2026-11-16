"""Text-to-speech with the built-in Windows voices (pyttsx3, local and free).

Only an English-readable version of each reply is spoken (see core.script.speakable); the
screen always shows the exact text."""
from __future__ import annotations

from typing import Any

from assistant.core.script import speakable


class Speaker:
    def __init__(self, voice: str | None = None, rate: int | None = None, engine: Any = None) -> None:
        self._engine = engine
        self.voice = voice
        self.rate = rate

    def _get_engine(self) -> Any:
        if self._engine is None:
            import pyttsx3
            self._engine = pyttsx3.init()
            if self.rate:
                self._engine.setProperty("rate", self.rate)
            if self.voice:
                for v in self._engine.getProperty("voices"):
                    if self.voice.lower() in (v.name or "").lower():
                        self._engine.setProperty("voice", v.id)
                        break
        return self._engine

    def say(self, text: str) -> None:
        spoken = speakable(text)
        if not spoken:
            return
        try:
            engine = self._get_engine()
            engine.say(spoken)
            engine.runAndWait()
        except Exception:
            pass  # speech is a nicety; the text is already on screen
