"""Groq Whisper (free tier). Key read from .env and passed explicitly (never put into os.environ)."""
from __future__ import annotations

import io
import wave
from typing import Any

import groq
import numpy as np

from assistant.core.config import Config
from assistant.interfaces.stt.base import SAMPLE_RATE, STTError, STTProvider


def to_wav_bytes(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bytes:
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


class GroqSTT(STTProvider):
    name = "groq"
    label = "Groq"

    def __init__(self, api_key: str, model: str = "whisper-large-v3-turbo", client: Any = None) -> None:
        self.model = model
        self.client = client or groq.Groq(api_key=api_key, max_retries=0, timeout=10.0)

    def transcribe(self, audio: np.ndarray, language: str | None, prompt: str | None) -> str:
        params: dict[str, Any] = {"model": self.model, "response_format": "json", "temperature": 0.0}
        if language:
            params["language"] = language
        if prompt:
            params["prompt"] = prompt
        try:
            result = self.client.audio.transcriptions.create(
                file=("command.wav", to_wav_bytes(audio)), **params)
        except groq.RateLimitError as e:
            raise STTError("Groq's speech recognition is rate limited right now.") from e
        except groq.AuthenticationError as e:
            raise STTError("My Groq key was rejected, so please check GROQ_API_KEY in .env.") from e
        except groq.APIConnectionError as e:
            raise STTError("I can't reach Groq for speech recognition.") from e
        except groq.APIStatusError as e:
            raise STTError(f"Groq speech recognition returned an error ({e.status_code}).") from e
        return (getattr(result, "text", "") or "").strip()


def create(config: Config) -> GroqSTT:
    settings = config.settings.get("stt", {}).get("groq", {})
    key_name = settings.get("api_key_env", "GROQ_API_KEY")
    api_key = config.secret(key_name)
    if not api_key:
        raise STTError(f"No {key_name} in .env, so I can't use Groq speech recognition.")
    return GroqSTT(api_key=api_key, model=settings.get("model", "whisper-large-v3-turbo"))
