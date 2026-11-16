"""Microphone recording (16 kHz mono float32) and start/stop beeps."""
from __future__ import annotations

import threading
from typing import Any

import numpy as np

from assistant.interfaces.stt.base import SAMPLE_RATE


def beep(kind: str = "start") -> None:
    """Short beep: higher pitch on start, lower on stop. Never raises."""
    freq = 880 if kind == "start" else 620
    try:
        import winsound
        winsound.Beep(freq, 70)
    except Exception:
        pass


class Recorder:
    def __init__(self, sample_rate: int = SAMPLE_RATE, stream_factory: Any = None) -> None:
        self.sample_rate = sample_rate
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream = None
        self._stream_factory = stream_factory

    def _callback(self, indata, frames, time_info, status) -> None:
        with self._lock:
            self._chunks.append(indata[:, 0].copy())

    def start(self) -> None:
        with self._lock:
            self._chunks = []
        factory = self._stream_factory
        if factory is None:
            import sounddevice as sd
            factory = sd.InputStream
        self._stream = factory(samplerate=self.sample_rate, channels=1, dtype="float32",
                               callback=self._callback)
        self._stream.start()

    def stop(self) -> np.ndarray:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            audio = np.concatenate(self._chunks) if self._chunks else np.zeros(0, dtype=np.float32)
            self._chunks = []
        return audio.astype(np.float32)

    def seconds(self, audio: np.ndarray) -> float:
        return len(audio) / float(self.sample_rate)
