"""Speech-to-text with provider fallback and a Devanagari guard.

Order: primary provider (Groq) -> fallback provider (local faster-whisper) on any failure.
Script guard: if the text contains Devanagari, the same audio is transcribed again with
`retry_language` (Urdu script). If it is still Devanagari, the text is dropped and the user
is asked to repeat. Devanagari never leaves this module.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field

import numpy as np

from assistant.core.config import Config
from assistant.core.script import has_devanagari
from assistant.interfaces.stt.base import STTError, STTProvider


@dataclass
class Transcript:
    text: str = ""                                   # never contains Devanagari
    provider: str | None = None
    notices: list[str] = field(default_factory=list)  # one-sentence messages for the user


class Transcriber:
    def __init__(self, primary: STTProvider | None, fallback: STTProvider | None,
                 language: str | None = None, prompt: str | None = None,
                 retry_language: str | None = "ur") -> None:
        self.primary = primary
        self.fallback = fallback
        self.language = language or None
        self.prompt = prompt or None
        self.retry_language = retry_language or None

    def _with_fallback(self, audio: np.ndarray, language: str | None, prompt: str | None,
                       notices: list[str]) -> tuple[str, str | None]:
        providers = [p for p in (self.primary, self.fallback) if p is not None]
        for i, provider in enumerate(providers):
            try:
                text = provider.transcribe(audio, language, prompt)
                if i > 0 and self.primary is not None:
                    notices.append(f"{self.primary.label} is unavailable, so I used {provider.label}.")
                return text, provider.name
            except STTError as e:
                if i == len(providers) - 1:
                    notices.append(str(e) if len(providers) == 1 else
                                   "I couldn't transcribe that, so please try again or use --text mode.")
        return "", None

    def transcribe(self, audio: np.ndarray) -> Transcript:
        notices: list[str] = []
        text, provider = self._with_fallback(audio, self.language, self.prompt, notices)

        if has_devanagari(text) and self.retry_language:
            text, provider = self._with_fallback(audio, self.retry_language, None, notices)

        if has_devanagari(text):
            notices.append("I heard that in the wrong script, so please say it again.")
            text = ""
        return Transcript(text=text, provider=provider, notices=notices)

    def warm_up(self) -> None:
        if self.fallback is not None:
            self.fallback.warm_up()


def _create(name: str, config: Config) -> STTProvider:
    module = importlib.import_module(f"{__name__}.{name}")
    return module.create(config)


def get_transcriber(config: Config) -> tuple[Transcriber, list[str]]:
    """Build the transcriber from settings.yaml; returns it plus startup notices."""
    stt = config.settings.get("stt", {})
    notices: list[str] = []
    providers: list[STTProvider | None] = []
    for key in ("provider", "fallback"):
        name = stt.get(key)
        if not name:
            providers.append(None)
            continue
        try:
            providers.append(_create(name, config))
        except STTError as e:
            notices.append(str(e))
            providers.append(None)
        except ModuleNotFoundError:
            notices.append(f"Unknown speech provider '{name}' in settings.yaml.")
            providers.append(None)
    primary, fallback = providers
    if primary is None and fallback is not None:
        primary, fallback = fallback, None
    return Transcriber(primary, fallback, stt.get("language"), stt.get("prompt"),
                       stt.get("retry_language", "ur")), notices
