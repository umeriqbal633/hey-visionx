"""Offline speech-to-text with faster-whisper on the CPU (free, local fallback).

Audio is passed as a numpy array, so faster-whisper never decodes files itself (its file
decoder is incompatible with av 19). ctranslate2 is pinned to 4.8.5 because Smart App
Control blocks the newer 4.9.0 DLL on this PC.
"""
from __future__ import annotations

import os
import threading
from typing import Any

import numpy as np

from assistant.core.config import Config
from assistant.interfaces.stt.base import STTError, STTProvider

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")  # harmless model-cache warning on Windows


class LocalSTT(STTProvider):
    name = "local"
    label = "offline transcription"

    def __init__(self, model_size: str = "small", compute_type: str = "int8",
                 cpu_threads: int = 0, model: Any = None) -> None:
        self.model_size = model_size
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self._model = model
        self._lock = threading.Lock()

    def _load(self) -> Any:
        with self._lock:
            if self._model is None:
                try:
                    from faster_whisper import WhisperModel
                    self._model = WhisperModel(self.model_size, device="cpu",
                                               compute_type=self.compute_type, cpu_threads=self.cpu_threads)
                except Exception as e:  # missing DLLs, blocked DLLs, no model download, ...
                    raise STTError("Offline transcription isn't available on this PC right now.") from e
            return self._model

    def warm_up(self) -> None:
        threading.Thread(target=self._safe_load, daemon=True).start()

    def _safe_load(self) -> None:
        try:
            self._load()
        except STTError:
            pass

    def transcribe(self, audio: np.ndarray, language: str | None, prompt: str | None) -> str:
        model = self._load()
        try:
            segments, _ = model.transcribe(audio.astype(np.float32), language=language or None,
                                           initial_prompt=prompt or None, beam_size=1, vad_filter=False)
            return " ".join(s.text.strip() for s in segments).strip()
        except Exception as e:
            raise STTError("Offline transcription failed.") from e


def create(config: Config) -> LocalSTT:
    settings = config.settings.get("stt", {}).get("local", {})
    return LocalSTT(model_size=settings.get("model", "small"),
                    compute_type=settings.get("compute_type", "int8"),
                    cpu_threads=int(settings.get("cpu_threads", 0)))
