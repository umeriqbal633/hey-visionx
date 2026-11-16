"""Speech-to-text provider interface. One file per provider in this package, each with a
`create(config) -> STTProvider` function; the provider name in settings.yaml is the file name."""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

SAMPLE_RATE = 16000  # all audio passed to providers is float32 mono at 16 kHz


class STTError(Exception):
    """A provider failure, already phrased as one short sentence for the user."""


class STTProvider(ABC):
    name: str = "stt"
    label: str = "speech recognition"   # used in user-facing sentences

    @abstractmethod
    def transcribe(self, audio: np.ndarray, language: str | None, prompt: str | None) -> str:
        """Return the transcript. Raise STTError on failure."""

    def warm_up(self) -> None:
        """Optional: load models ahead of time."""
